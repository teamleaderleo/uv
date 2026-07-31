#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

TARGETS = (
    Path("crates/uv-install-wheel/src/wheel.rs"),
    Path("crates/uv-virtualenv/src/virtualenv.rs"),
    Path("crates/uv/src/commands/project/run.rs"),
)

replacement_totals = {"realpath --": 0, "dirname --": 0}

for path in TARGETS:
    text = path.read_text()
    counts = {needle: text.count(needle) for needle in replacement_totals}
    if counts["realpath --"] == 0:
        raise SystemExit(f"expected at least one relocatable realpath delimiter in {path}")

    updated = text.replace("realpath --", "realpath").replace("dirname --", "dirname")
    if updated == text:
        raise SystemExit(f"candidate made no change in {path}")
    if "realpath --" in updated or "dirname --" in updated:
        raise SystemExit(f"launcher delimiter remains in {path}")

    path.write_text(updated)
    for needle, count in counts.items():
        replacement_totals[needle] += count
    print(
        f"{path}: realpath={counts['realpath --']} dirname={counts['dirname --']}"
    )

if replacement_totals["realpath --"] < len(TARGETS):
    raise SystemExit("candidate did not update every generator")

print(
    "FIELDWORK_307_PATCH="
    f"realpath:{replacement_totals['realpath --']},"
    f"dirname:{replacement_totals['dirname --']}"
)
