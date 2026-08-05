#!/usr/bin/env python3
"""Measure warm same-wheel cache-hit cost with and without per-wheel locks."""

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


PACKAGE = "fieldwork-lock-bench"
MODULE = "fieldwork_lock_bench"
VERSION = "0.0.1"


def record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"sha256={digest.decode('ascii')}"


def build_wheel(destination: Path) -> Path:
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
            "Generator: fieldwork-lock-bench\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
    }
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


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def create_venv(uv: str, venv: Path, *, cwd: Path, env: dict[str, str]) -> None:
    if venv.exists():
        shutil.rmtree(venv)
    run([uv, "venv", str(venv)], cwd=cwd, env=env)


def install_command(uv: str, venv: Path, wheel: Path) -> list[str]:
    return [
        uv,
        "-vv",
        "pip",
        "install",
        "--python",
        str(venv_python(venv)),
        "--link-mode",
        "copy",
        str(wheel),
    ]


def prepare(uv: str, label: str, root: Path, wheel: Path) -> dict[str, Any]:
    case = root / label
    case.mkdir(parents=True)
    cache = case / "cache"
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(cache)
    env["UV_NO_PROGRESS"] = "1"

    prime = case / "prime"
    create_venv(uv, prime, cwd=case, env=env)
    run(install_command(uv, prime, wheel), cwd=case, env=env)
    return {"uv": uv, "label": label, "case": case, "env": env}


def run_batch(
    prepared: dict[str, Any],
    wheel: Path,
    concurrency: int,
    repeat: int,
) -> dict[str, Any]:
    venvs = []
    for index in range(concurrency):
        venv = prepared["case"] / f"batch-{concurrency}-{repeat}-{index}"
        create_venv(prepared["uv"], venv, cwd=prepared["case"], env=prepared["env"])
        venvs.append(venv)

    started_ns = time.perf_counter_ns()
    processes: list[subprocess.Popen[str]] = []
    for venv in venvs:
        processes.append(
            subprocess.Popen(
                install_command(prepared["uv"], venv, wheel),
                cwd=prepared["case"],
                env=prepared["env"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )

    receipts = []
    for process in processes:
        stdout, stderr = process.communicate()
        receipts.append(
            {
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "cache_hit": "already cached" in stderr,
            }
        )
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000

    if any(receipt["returncode"] != 0 for receipt in receipts):
        raise RuntimeError(f"{prepared['label']} batch failed: {receipts}")
    if not all(receipt["cache_hit"] for receipt in receipts):
        raise RuntimeError(f"{prepared['label']} batch missed cache: {receipts}")

    for venv in venvs:
        run(
            [
                str(venv_python(venv)),
                "-c",
                f"import {MODULE}; assert {MODULE}.VALUE == 1",
            ],
            cwd=prepared["case"],
            env=prepared["env"],
        )

    return {
        "label": prepared["label"],
        "concurrency": concurrency,
        "repeat": repeat,
        "elapsed_ms": elapsed_ms,
        "cache_hits": [receipt["cache_hit"] for receipt in receipts],
    }


def benchmark_pair(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    wheel: Path,
    concurrency: int,
    repeats: int,
) -> dict[str, Any]:
    samples: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
    execution_order: list[list[str]] = []
    prepared = {"baseline": baseline, "candidate": candidate}

    for repeat in range(repeats):
        order = ["baseline", "candidate"] if repeat % 2 == 0 else ["candidate", "baseline"]
        execution_order.append(order)
        for label in order:
            samples[label].append(run_batch(prepared[label], wheel, concurrency, repeat))

    baseline_times = [sample["elapsed_ms"] for sample in samples["baseline"]]
    candidate_times = [sample["elapsed_ms"] for sample in samples["candidate"]]
    baseline_median = statistics.median(baseline_times)
    candidate_median = statistics.median(candidate_times)
    return {
        "concurrency": concurrency,
        "repeats": repeats,
        "execution_order": execution_order,
        "baseline": {"samples": samples["baseline"], "median_ms": baseline_median},
        "candidate": {"samples": samples["candidate"], "median_ms": candidate_median},
        "median_delta_ms": candidate_median - baseline_median,
        "candidate_to_baseline_median_ratio": candidate_median / baseline_median,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-uv", required=True)
    parser.add_argument("--candidate-uv", required=True)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8])
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    baseline_uv = str(Path(args.baseline_uv).resolve())
    candidate_uv = str(Path(args.candidate_uv).resolve())
    root = Path(tempfile.mkdtemp(prefix="uv-generation-lock-benchmark-"))
    try:
        wheel_dir = root / "wheel"
        wheel_dir.mkdir()
        wheel = build_wheel(wheel_dir)
        baseline = prepare(baseline_uv, "baseline", root, wheel)
        candidate = prepare(candidate_uv, "candidate", root, wheel)
        cases = [
            benchmark_pair(
                baseline,
                candidate,
                wheel,
                concurrency,
                args.repeats,
            )
            for concurrency in args.concurrency
        ]
        print(
            json.dumps(
                {
                    "evidence_class": "target-executed-balanced-warm-lock-comparison",
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
