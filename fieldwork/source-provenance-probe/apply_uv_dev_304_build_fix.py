#!/usr/bin/env python3
"""Verify that the retained uv-dev #304 diff already carries its syntax fix."""

from pathlib import Path


path = Path("crates/uv-resolver/src/lock/mod.rs")
text = path.read_text(encoding="utf-8")

missing_semicolon = """                        .collect::<Result<_, _>>()?
                    Ok::<_, LockError>((group.clone(), requirements))
"""
current_form = """                        .collect::<Result<_, _>>()?;
                    Ok::<_, LockError>((group.clone(), requirements))
"""

if missing_semicolon in text:
    raise SystemExit("uv-dev #304 still contains the missing-semicolon form")
if text.count(current_form) != 1:
    raise SystemExit(
        "uv-dev #304 syntax audit mismatch: expected one corrected dependency-group collect"
    )

print("uv-dev #304 already contains the required semicolon")
