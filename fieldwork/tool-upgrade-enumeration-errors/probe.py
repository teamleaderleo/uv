#!/usr/bin/env python3
"""Probe whether `uv tool upgrade --all` hides inventory enumeration failures."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any


def run(uv: str, root: Path) -> dict[str, Any]:
    tool_dir = root / "tools"
    bin_dir = root / "bin"
    tool_dir.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (tool_dir / "not a valid package name!").mkdir()

    env = os.environ.copy()
    env["UV_TOOL_DIR"] = str(tool_dir)
    env["XDG_BIN_HOME"] = str(bin_dir)
    env["PATH"] = str(bin_dir)
    env["UV_NO_PROGRESS"] = "1"

    completed = subprocess.run(
        [uv, "tool", "upgrade", "--all"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": [uv, "tool", "upgrade", "--all"],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "reported_inventory_error": "Not a valid package or extra name" in completed.stderr,
        "reported_nothing_to_upgrade": "Nothing to upgrade" in completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True)
    parser.add_argument("--expect", choices=["hidden", "failed"], required=True)
    args = parser.parse_args()

    uv = str(Path(args.uv).resolve())
    with tempfile.TemporaryDirectory(prefix="uv-tool-upgrade-enumeration-") as temp:
        result = run(uv, Path(temp))
    result["expectation"] = args.expect
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.expect == "hidden":
        return (
            0
            if result["returncode"] == 0
            and result["reported_nothing_to_upgrade"]
            and not result["reported_inventory_error"]
            else 1
        )
    return (
        0
        if result["returncode"] != 0
        and result["reported_inventory_error"]
        and not result["reported_nothing_to_upgrade"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
