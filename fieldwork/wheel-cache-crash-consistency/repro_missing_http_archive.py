#!/usr/bin/env python3
"""Probe whether an HTTP wheel cache pointer heals a missing extracted archive."""

from __future__ import annotations

import argparse
import base64
import csv
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Any
import zipfile


PACKAGE_NAME = "fieldwork-cache-missing-http-archive"
MODULE_NAME = "fieldwork_cache_missing_http_archive"
VERSION = "0.0.1"


def record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"sha256={digest.decode('ascii')}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_wheel(destination: Path) -> Path:
    dist_info = f"{MODULE_NAME}-{VERSION}.dist-info"
    wheel = destination / f"{MODULE_NAME}-{VERSION}-py3-none-any.whl"
    files: dict[str, bytes] = {
        f"{MODULE_NAME}/__init__.py": b"VALUE = 1\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {PACKAGE_NAME}\n"
            f"Version: {VERSION}\n\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: fieldwork-cache-missing-http-archive\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
    }

    record_buffer = io.StringIO(newline="")
    writer = csv.writer(record_buffer, lineterminator="\n")
    for path, data in files.items():
        writer.writerow([path, record_digest(data), str(len(data))])
    writer.writerow([f"{dist_info}/RECORD", "", ""])
    files[f"{dist_info}/RECORD"] = record_buffer.getvalue().encode()

    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return wheel


def venv_python(venv: Path) -> Path:
    windows = venv / "Scripts" / "python.exe"
    return windows if windows.exists() else venv / "bin" / "python"


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def install_once(
    uv: str,
    work: Path,
    cache: Path,
    wheel_url: str,
    venv_name: str,
) -> tuple[Path, list[dict[str, Any]]]:
    venv = work / venv_name
    if venv.exists():
        shutil.rmtree(venv)
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(cache)
    env["UV_NO_PROGRESS"] = "1"

    create = run([uv, "venv", str(venv)], cwd=work, env=env)
    if create["returncode"] != 0:
        return venv, [create]
    install = run(
        [
            uv,
            "-vv",
            "pip",
            "install",
            "--python",
            str(venv_python(venv)),
            wheel_url,
        ],
        cwd=work,
        env=env,
    )
    return venv, [create, install]


def verify_install(venv: Path, work: Path) -> dict[str, Any]:
    script = (
        "import importlib.metadata, json\n"
        f"import {MODULE_NAME}\n"
        "print(json.dumps({"
        f"'version': importlib.metadata.version('{PACKAGE_NAME}'),"
        f"'value': {MODULE_NAME}.VALUE"
        "}))\n"
    )
    return run(
        [str(venv_python(venv)), "-c", script],
        cwd=work,
        env=os.environ.copy(),
    )


def successful_install(steps: list[dict[str, Any]]) -> bool:
    return len(steps) == 2 and steps[-1]["returncode"] == 0


def successful_verification(result: dict[str, Any] | None) -> bool:
    if result is None or result["returncode"] != 0:
        return False
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return False
    return payload == {"version": VERSION, "value": 1}


def archive_roots(cache: Path) -> list[Path]:
    pattern = f"archive-v*/**/{MODULE_NAME}-{VERSION}.dist-info/METADATA"
    roots: set[Path] = set()
    for metadata in cache.glob(pattern):
        if not metadata.is_file():
            continue
        root = next(
            parent
            for parent in metadata.parents
            if parent.parent.name.startswith("archive-v")
        )
        roots.add(root)
    return sorted(roots)


def pointer_receipts(cache: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for pointer in sorted(cache.rglob("*.http")):
        if pointer.is_file():
            stat = pointer.stat()
            receipts.append(
                {
                    "path": str(pointer.relative_to(cache)),
                    "size": stat.st_size,
                    "sha256": sha256(pointer),
                    "inode": getattr(stat, "st_ino", None),
                }
            )
    return receipts


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", default="uv", help="uv executable to probe")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    uv = str(Path(args.uv).resolve()) if os.sep in args.uv else args.uv

    temp = Path(tempfile.mkdtemp(prefix="uv-cache-missing-http-archive-probe-"))
    server: ThreadingHTTPServer | None = None
    thread: threading.Thread | None = None
    try:
        wheel_dir = temp / "wheel"
        wheel_dir.mkdir()
        wheel = build_wheel(wheel_dir)
        wheel_before = {"size": wheel.stat().st_size, "sha256": sha256(wheel)}

        handler = functools.partial(QuietHandler, directory=str(wheel_dir))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        wheel_url = f"http://{host}:{port}/{wheel.name}"

        work = temp / "work"
        cache = work / "cache"
        work.mkdir()

        first_venv, first_install = install_once(
            uv, work, cache, wheel_url, "venv-first"
        )
        first_verify = (
            verify_install(first_venv, work)
            if successful_install(first_install)
            else None
        )
        roots_before = archive_roots(cache)
        pointers_before = pointer_receipts(cache)

        if (
            not successful_install(first_install)
            or not successful_verification(first_verify)
            or len(roots_before) != 1
            or not pointers_before
        ):
            print(
                json.dumps(
                    {
                        "outcome": "probe-failure",
                        "reason": "first install, verification, archive discovery, or pointer discovery failed",
                        "first_install": first_install,
                        "first_verification": first_verify,
                        "archive_roots_before": [str(path) for path in roots_before],
                        "pointers_before": pointers_before,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2

        removed_root = roots_before[0]
        removed_root_relative = str(removed_root.relative_to(cache))
        removed_root_absolute = str(removed_root)
        shutil.rmtree(removed_root)

        second_venv, second_install = install_once(
            uv, work, cache, wheel_url, "venv-second"
        )
        second_verify = (
            verify_install(second_venv, work)
            if successful_install(second_install)
            else None
        )
        roots_after = archive_roots(cache)
        pointers_after = pointer_receipts(cache)
        wheel_after = {"size": wheel.stat().st_size, "sha256": sha256(wheel)}

        recovered = (
            successful_install(second_install)
            and successful_verification(second_verify)
            and len(roots_after) == 1
            and str(roots_after[0].relative_to(cache)) != removed_root_relative
        )
        stale_pointer_survived = pointers_before == pointers_after
        second_failure_text = "\n".join(
            f"{step['stdout']}\n{step['stderr']}" for step in second_install
        )
        second_failure_mentions_removed_archive = (
            removed_root_relative in second_failure_text
            or removed_root_absolute in second_failure_text
        )

        if recovered:
            outcome = "recovered"
        elif (
            not successful_install(second_install)
            and second_failure_mentions_removed_archive
        ):
            outcome = "bug-reproduced"
        elif successful_install(second_install) and not successful_verification(second_verify):
            outcome = "bug-reproduced"
        else:
            outcome = "inconclusive"

        receipt = {
            "evidence_class": "target-executed-missing-http-archive-model",
            "outcome": outcome,
            "source_wheel_unchanged": wheel_before == wheel_after,
            "wheel_before": wheel_before,
            "wheel_after": wheel_after,
            "wheel_url": wheel_url,
            "removed_archive_root": removed_root_relative,
            "removed_archive_exists_after_delete": removed_root.exists(),
            "archive_roots_after_retry": [
                str(path.relative_to(cache)) for path in roots_after
            ],
            "pointers_before": pointers_before,
            "pointers_after": pointers_after,
            "stale_pointer_survived": stale_pointer_survived,
            "second_failure_mentions_removed_archive": second_failure_mentions_removed_archive,
            "first_install": first_install,
            "first_verification": first_verify,
            "second_install": second_install,
            "second_verification": second_verify,
        }
        print(json.dumps(receipt, indent=2, sort_keys=True))

        if outcome == "inconclusive":
            return 3
        return 0
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        if args.keep:
            print(f"kept probe directory: {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
