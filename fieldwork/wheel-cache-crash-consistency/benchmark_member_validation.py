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


def prepare_case(
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

    venvs: list[Path] = []
    for index in range(repeats):
        venv = case / f"timed-{index}"
        create_venv(uv, venv, cwd=case, env=env)
        venvs.append(venv)

    return {
        "uv": uv,
        "label": label,
        "case": case,
        "env": env,
        "venvs": venvs,
        "durations_ms": [],
        "cache_hit_receipts": [],
    }


def measure_once(prepared: dict[str, Any], wheel: Path, index: int) -> None:
    started = time.perf_counter_ns()
    completed = install(
        prepared["uv"],
        prepared["venvs"][index],
        wheel,
        cwd=prepared["case"],
        env=prepared["env"],
    )
    prepared["durations_ms"].append(
        (time.perf_counter_ns() - started) / 1_000_000
    )
    prepared["cache_hit_receipts"].append("already cached" in completed.stderr)


def summarize_case(
    prepared: dict[str, Any],
    member_count: int,
    repeats: int,
) -> dict[str, Any]:
    durations_ms = prepared["durations_ms"]
    cache_hit_receipts = prepared["cache_hit_receipts"]
    verification = run(
        [
            str(venv_python(prepared["venvs"][-1])),
            "-c",
            f"import {MODULE}; assert {MODULE}.VALUE == 1",
        ],
        cwd=prepared["case"],
        env=prepared["env"],
    )

    if not all(cache_hit_receipts):
        raise RuntimeError(
            f"{prepared['label']} did not report a cache hit for every timed run: "
            f"{cache_hit_receipts}"
        )

    return {
        "label": prepared["label"],
        "member_count": member_count,
        "repeats": repeats,
        "durations_ms": durations_ms,
        "median_ms": statistics.median(durations_ms),
        "minimum_ms": min(durations_ms),
        "maximum_ms": max(durations_ms),
        "cache_hit_receipts": cache_hit_receipts,
        "verification_returncode": verification.returncode,
    }


def benchmark_pair(
    baseline_uv: str,
    candidate_uv: str,
    root: Path,
    wheel: Path,
    member_count: int,
    repeats: int,
) -> dict[str, Any]:
    prepared = {
        "baseline": prepare_case(
            baseline_uv,
            "baseline",
            root,
            wheel,
            member_count,
            repeats,
        ),
        "candidate": prepare_case(
            candidate_uv,
            "candidate",
            root,
            wheel,
            member_count,
            repeats,
        ),
    }

    execution_order: list[list[str]] = []
    for index in range(repeats):
        order = (
            ["baseline", "candidate"]
            if index % 2 == 0
            else ["candidate", "baseline"]
        )
        execution_order.append(order)
        for label in order:
            measure_once(prepared[label], wheel, index)

    baseline = summarize_case(prepared["baseline"], member_count, repeats)
    candidate = summarize_case(prepared["candidate"], member_count, repeats)
    return {
        "member_count": member_count,
        "execution_order": execution_order,
        "baseline": baseline,
        "candidate": candidate,
        "candidate_to_baseline_median_ratio": (
            candidate["median_ms"] / baseline["median_ms"]
        ),
        "median_delta_ms": candidate["median_ms"] - baseline["median_ms"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-uv", required=True)
    parser.add_argument("--candidate-uv", required=True)
    parser.add_argument("--repeats", type=int, default=6)
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
            cases.append(
                benchmark_pair(
                    baseline_uv,
                    candidate_uv,
                    root,
                    wheel,
                    member_count,
                    args.repeats,
                )
            )

        print(
            json.dumps(
                {
                    "evidence_class": "target-executed-balanced-warm-cache-comparison",
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
