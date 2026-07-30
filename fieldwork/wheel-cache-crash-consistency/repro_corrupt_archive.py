#!/usr/bin/env python3
"""Probe whether uv reuses a deliberately corrupted extracted-wheel cache entry."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"sha256={digest.decode('ascii')}"


def build_wheel(destination: Path) -> Path:
    name = "fieldwork-cache-probe"
    normalized = "fieldwork_cache_probe"
    version = "0.0.1"
    dist_info = f"{normalized}-{version}.dist-info"
    wheel = destination / f"{normalized}-{version}-py3-none-any.whl"

    files: dict[str, bytes] = {
        f"{normalized}/__init__.py": b"VALUE = 1\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: fieldwork-cache-probe\n"
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


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
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


def install_once(uv: str, work: Path, cache: Path, wheel: Path) -> list[dict[str, object]]:
    venv = work / ".venv"
    if venv.exists():
        shutil.rmtree(venv)
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(cache)
    env["UV_NO_PROGRESS"] = "1"

    create = run([uv, "venv", str(venv)], cwd=work, env=env)
    if create["returncode"] != 0:
        return [create]
    install = run(
        [uv, "pip", "install", "--python", str(venv_python(venv)), str(wheel)],
        cwd=work,
        env=env,
    )
    return [create, install]


def matching_metadata(cache: Path) -> list[Path]:
    return sorted(
        path
        for path in cache.glob(
            "archive-v*/**/fieldwork_cache_probe-0.0.1.dist-info/METADATA"
        )
        if path.is_file()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", default="uv", help="uv executable to probe")
    parser.add_argument(
        "--keep", action="store_true", help="keep the temporary directory for inspection"
    )
    args = parser.parse_args()

    temp = Path(tempfile.mkdtemp(prefix="uv-cache-crash-probe-"))
    try:
        work = temp / "work"
        cache = temp / "cache"
        work.mkdir()
        wheel = build_wheel(work)

        first = install_once(args.uv, work, cache, wheel)
        metadata = matching_metadata(cache)
        if not metadata:
            print(
                json.dumps(
                    {
                        "result": "no-matching-extracted-archive",
                        "root": str(temp),
                        "first_install": first,
                    },
                    indent=2,
                )
            )
            return 2

        before = {str(path): path.stat().st_size for path in metadata}
        for path in metadata:
            path.write_bytes(b"")
        after = {str(path): path.stat().st_size for path in metadata}

        second = install_once(args.uv, work, cache, wheel)
        second_install = second[-1]
        output = {
            "result": (
                "corrupt-cache-reused"
                if second_install["returncode"] != 0
                else "install-recovered-or-reextracted"
            ),
            "root": str(temp),
            "metadata_sizes_before": before,
            "metadata_sizes_after": after,
            "first_install": first,
            "second_install": second,
        }
        print(json.dumps(output, indent=2))
        return 0 if second_install["returncode"] != 0 else 1
    finally:
        if args.keep:
            print(f"kept probe directory: {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
