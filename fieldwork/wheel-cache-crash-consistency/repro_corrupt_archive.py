#!/usr/bin/env python3
"""Execute isolated uv extracted-wheel cache corruption scenarios."""

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
from typing import Any
import zipfile


PACKAGE_NAME = "fieldwork-cache-probe"
MODULE_NAME = "fieldwork_cache_probe"
VERSION = "0.0.1"
CORRUPTION_SENTINEL = "fieldwork cached module corruption"


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
            f"Version: {VERSION}\n"
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
    wheel: Path,
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
            str(wheel),
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


def matching_archive_files(cache: Path) -> list[dict[str, Path]]:
    archives: list[dict[str, Path]] = []
    metadata_pattern = f"archive-v*/**/{MODULE_NAME}-{VERSION}.dist-info/METADATA"
    for metadata in sorted(cache.glob(metadata_pattern)):
        module = metadata.parent.parent / MODULE_NAME / "__init__.py"
        if metadata.is_file() and module.is_file():
            archive_root = next(
                parent
                for parent in metadata.parents
                if parent.parent.name.startswith("archive-v")
            )
            archives.append(
                {
                    "root": archive_root,
                    "metadata": metadata,
                    "module": module,
                }
            )
    return archives


def file_receipt(path: Path, cache: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.relative_to(cache)),
        "size": stat.st_size,
        "sha256": sha256(path),
        "inode": getattr(stat, "st_ino", None),
        "device": getattr(stat, "st_dev", None),
    }


def archive_receipt(archive: dict[str, Path], cache: Path) -> dict[str, Any]:
    return {
        "root": str(archive["root"].relative_to(cache)),
        "metadata": file_receipt(archive["metadata"], cache),
        "module": file_receipt(archive["module"], cache),
    }


def successful_install(steps: list[dict[str, Any]]) -> bool:
    return len(steps) == 2 and steps[-1]["returncode"] == 0


def successful_verification(verification: dict[str, Any]) -> bool:
    if verification["returncode"] != 0:
        return False
    try:
        payload = json.loads(verification["stdout"])
    except json.JSONDecodeError:
        return False
    return payload == {"version": VERSION, "value": 1}


def run_scenario(uv: str, root: Path, wheel: Path, mode: str) -> dict[str, Any]:
    work = root / mode
    cache = work / "cache"
    work.mkdir(parents=True)

    first_venv, first = install_once(uv, work, cache, wheel, "venv-first")
    first_verify = verify_install(first_venv, work) if successful_install(first) else None
    if not successful_install(first) or not first_verify or not successful_verification(first_verify):
        return {
            "mode": mode,
            "outcome": "probe-failure",
            "reason": "first install or verification failed",
            "first_install": first,
            "first_verification": first_verify,
        }

    archives = matching_archive_files(cache)
    if len(archives) != 1:
        return {
            "mode": mode,
            "outcome": "probe-failure",
            "reason": f"expected one matching extracted archive, found {len(archives)}",
            "first_install": first,
            "first_verification": first_verify,
        }

    archive = archives[0]
    before = archive_receipt(archive, cache)

    if mode == "metadata-zero":
        archive["metadata"].write_bytes(b"")
    elif mode == "module-corrupt":
        archive["module"].write_text(
            f"raise RuntimeError({CORRUPTION_SENTINEL!r})\n",
            encoding="utf-8",
        )
    elif mode != "clean-control":
        raise ValueError(mode)

    after_corruption = archive_receipt(archive, cache)
    second_venv, second = install_once(uv, work, cache, wheel, "venv-second")
    second_verify = verify_install(second_venv, work) if successful_install(second) else None
    final_archives = [
        archive_receipt(candidate, cache) for candidate in matching_archive_files(cache)
    ]

    same_root_final = next(
        (item for item in final_archives if item["root"] == before["root"]),
        None,
    )
    archive_repaired = (
        same_root_final is not None
        and same_root_final["metadata"]["sha256"] == before["metadata"]["sha256"]
        and same_root_final["module"]["sha256"] == before["module"]["sha256"]
    )
    archive_replaced = (
        same_root_final is None
        or (
            same_root_final["metadata"]["inode"],
            same_root_final["module"]["inode"],
        )
        != (before["metadata"]["inode"], before["module"]["inode"])
    )
    healthy_replacements = [
        item
        for item in final_archives
        if item["root"] != before["root"]
        and item["metadata"]["sha256"] == before["metadata"]["sha256"]
        and item["module"]["sha256"] == before["module"]["sha256"]
    ]
    archive_republished = bool(healthy_replacements)

    if mode == "clean-control":
        outcome = (
            "healthy-control"
            if successful_install(second)
            and second_verify is not None
            and successful_verification(second_verify)
            else "probe-failure"
        )
    elif successful_install(second) and second_verify is not None:
        if successful_verification(second_verify) and (
            archive_repaired or archive_replaced or archive_republished
        ):
            outcome = "recovered"
        elif successful_verification(second_verify):
            outcome = "inconclusive"
        else:
            outcome = "bug-reproduced"
    elif mode == "metadata-zero" and same_root_final is not None:
        outcome = "bug-reproduced"
    else:
        outcome = "inconclusive"

    return {
        "mode": mode,
        "outcome": outcome,
        "wheel": {
            "path": str(wheel),
            "size": wheel.stat().st_size,
            "sha256": sha256(wheel),
        },
        "archive_before": before,
        "archive_after_corruption": after_corruption,
        "archives_after_retry": final_archives,
        "archive_repaired": archive_repaired,
        "archive_replaced": archive_replaced,
        "archive_republished": archive_republished,
        "healthy_replacements": healthy_replacements,
        "first_install": first,
        "first_verification": first_verify,
        "second_install": second,
        "second_verification": second_verify,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", default="uv", help="uv executable to probe")
    parser.add_argument(
        "--keep", action="store_true", help="keep the temporary directory for inspection"
    )
    args = parser.parse_args()
    uv = str(Path(args.uv).resolve()) if os.sep in args.uv else args.uv

    temp = Path(tempfile.mkdtemp(prefix="uv-cache-crash-probe-"))
    try:
        wheel_dir = temp / "wheel"
        wheel_dir.mkdir()
        wheel = build_wheel(wheel_dir)
        scenarios = [
            run_scenario(uv, temp, wheel, "clean-control"),
            run_scenario(uv, temp, wheel, "metadata-zero"),
            run_scenario(uv, temp, wheel, "module-corrupt"),
        ]
        output = {
            "evidence_class": "target-executed-process-corruption-model",
            "power_loss_claim": False,
            "root": str(temp),
            "scenarios": scenarios,
        }
        print(json.dumps(output, indent=2, sort_keys=True))

        outcomes = {scenario["outcome"] for scenario in scenarios}
        if "probe-failure" in outcomes:
            return 2
        if "inconclusive" in outcomes:
            return 3
        return 0
    finally:
        if args.keep:
            print(f"kept probe directory: {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
