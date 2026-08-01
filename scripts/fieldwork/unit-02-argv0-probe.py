#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix="uv-unit-02-argv0-") as directory:
    root = Path(directory)
    script = root / "launcher"
    script.write_text("#!/bin/sh\nprintf 'argv0=%s\\n' \"$0\"\n")
    script.chmod(0o755)

    for requested_argv0 in ("-tool", "--help", "plain-name"):
        completed = subprocess.run(
            [requested_argv0],
            executable=str(script),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        print(
            f"direct requested={requested_argv0!r} status={completed.returncode} "
            f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
        )
        if completed.returncode != 0:
            raise SystemExit(f"direct shebang execution failed for argv0={requested_argv0!r}")
        prefix = "argv0="
        if not completed.stdout.startswith(prefix):
            raise SystemExit(f"unexpected direct output: {completed.stdout!r}")
        observed = completed.stdout[len(prefix) :].strip()
        if observed.startswith("-"):
            raise SystemExit(f"kernel exposed option-like argv0 to shell script: {observed!r}")
        if not os.path.samefile(observed, script):
            raise SystemExit(f"shell script argv0 did not resolve to script path: {observed!r}")

    option_like = root / "-tool"
    option_like.write_text("probe\n")
    for variant, command in (
        ("delimiter", 'realpath -- "$0"'),
        ("delimiter-free", 'realpath "$0"'),
    ):
        completed = subprocess.run(
            ["/bin/sh", "-c", command, "-tool"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        print(
            f"synthetic variant={variant} status={completed.returncode} "
            f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
        )

print("UNIT_02_DIRECT_SHEBANG_ARGV0=script-path")
print("UNIT_02_SYNTHETIC_BARE_ARGV0=observed-only")
