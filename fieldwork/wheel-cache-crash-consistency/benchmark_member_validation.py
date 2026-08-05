#!/usr/bin/env python3
"""Compare warm-cache install cost with and without extracted-member validation."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
from typing import Any
import zipfile


PACKAGE = "fieldwork-member-bench"
MODULE = "fieldwork_member_bench"
VERSION = "0.0.1"


def record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"sha256={digest.decode('ascii')}"


def build_wheel(destination: Path, member_count: int) -> Path:
    dist_info = f"{MODULE}-{VERSION}.dist-info"
    wheel = destination / f"{MODULE}-{VERSION}-py3-none-any.whl"
    files: dict[str, bytes] = {
        f"{MODULE}/__init__.py": b"VALUE = 1\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {PACKAGE}\n"
            f"Version: {VERSION}\n\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: fieldwork-member-bench\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
    }
    for index in range(member_count):
        files[f"{MODULE}/members/member_{index:05d}.py"] = (
            f"INDEX = {index}\n".encode()
        )

    record_buffer = io.StringIO(newline="")
    writer = csv.writer(record_buffer, lineterminator="\n")
    for relative, data in files.items():
        writer.writerow([relative, record_digest(data), str(len(data))])
    writer.writerow([f"{dist_info}/RECORD", "", ""])
    files[f"{dist_info}/RECORD"] = record_buffer.getvalue().encode()

    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in files.items():
            archive.writestr(relative, data)
    return wheel


def venv_python(venv: Path) -> Path:
    windows = venv / "Scripts" / "python.exe"
    return windows if windows.exists() else venv / "bin" / "python"


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def create_venv(uv: str, path: Path, *, cwd: Path, env: dict[str, str]) -> None:
    if path.exists():
        shutil.rmtree(path)
    run([uv, "venv", str(path)], cwd=cwd, env=env)


def install(
    uv: str,
    venv: Path,
    wheel: Path,
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            uv,
            "-vv",
            "pip",
            "install",
            "--python",
            str(venv_python(venv)),
            "--link-mode",
            "copy",
            str(wheel),
        ],
        cwd=cwd,
        env=env,
    )


def benchmark_case(
    uv: str,
    label: str,
    root: Path,
    wheel: Path,
    member_count: int,
    repeats: int,
) -> dict[str, Any]:
    case = root / f"{label}-{member_count}"
    cache = case / "cache"
    case.mkdir(parents=True)
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(cache)
    env["UV_NO_PROGRESS"] = "1"

    prime = case / "prime"
    create_venv(uv, prime, cwd=case, env=env)
    install(uv, prime, wheel, cwd=case, env=env)

    venvs = []
    for index in range(repeats):
        venv = case / f"timed-{index}"
        create_venv(uv, venv, cwd=case, env=env)
        venvs.append(venv)

    durations_ms: list[float] = []
    cache_hit_receipts: list[bool] = []
    for venv in venvs:
        started = time.perf_counter_ns()
        completed = install(uv, venv, wheel, cwd=case, env=env)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        durations_ms.append(elapsed_ms)
        cache_hit_receipts.append("already cached" in completed.stderr)

    verification = run(
        [
            str(venv_python(venvs[-1])),
            "-c",
            f"import {MODULE}; assert {MODULE}.VALUE == 1",
        ],
        cwd=case,
        env=env,
    )

    if not all(cache_hit_receipts):
        raise RuntimeError(
            f"{label} did not report a cache hit for every timed run: {cache_hit_receipts}"
        )

    return {
        "label": label,
        "member_count": member_count,
        "repeats": repeats,
        "durations_ms": durations_ms,
        "median_ms": statistics.median(durations_ms),
        "minimum_ms": min(durations_ms),
        "maximum_ms": max(durations_ms),
        "cache_hit_receipts": cache_hit_receipts,
        "verification_returncode": verification.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-uv", required=True)
    parser.add_argument("--candidate-uv", required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--counts", type=int, nargs="+", default=[100, 1000, 5000])
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    baseline_uv = str(Path(args.baseline_uv).resolve())
    candidate_uv = str(Path(args.candidate_uv).resolve())
    root = Path(tempfile.mkdtemp(prefix="uv-member-validation-benchmark-"))
    try:
        wheel_dir = root / "wheels"
        wheel_dir.mkdir()
        cases = []
        for member_count in args.counts:
            wheel = build_wheel(wheel_dir, member_count)
            baseline = benchmark_case(
                baseline_uv,
                "baseline",
                root,
                wheel,
                member_count,
                args.repeats,
            )
            candidate = benchmark_case(
                candidate_uv,
                "candidate",
                root,
                wheel,
                member_count,
                args.repeats,
            )
            cases.append(
                {
                    "member_count": member_count,
                    "baseline": baseline,
                    "candidate": candidate,
                    "candidate_to_baseline_median_ratio": (
                        candidate["median_ms"] / baseline["median_ms"]
                    ),
                    "median_delta_ms": candidate["median_ms"] - baseline["median_ms"],
                }
            )

        print(
            json.dumps(
                {
                    "evidence_class": "target-executed-warm-cache-comparison",
                    "threshold_enforced": False,
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "baseline_uv": baseline_uv,
                    "candidate_uv": candidate_uv,
                    "cases": cases,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        if args.keep:
            print(f"kept benchmark directory: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
