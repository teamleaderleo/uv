#!/usr/bin/env python3
"""Apply the isolated compile repair after the exact uv-dev #304 diff."""

from pathlib import Path

path = Path("crates/uv-resolver/src/lock/mod.rs")
text = path.read_text()
old = """                        .collect::<Result<_, _>>()?
                    Ok::<_, LockError>((group.clone(), requirements))
"""
new = """                        .collect::<Result<_, _>>()?;
                    Ok::<_, LockError>((group.clone(), requirements))
"""
if text.count(old) != 1:
    raise SystemExit(
        f"uv-dev #304 compile-repair fragment mismatch: expected 1, found {text.count(old)}"
    )
path.write_text(text.replace(old, new))
