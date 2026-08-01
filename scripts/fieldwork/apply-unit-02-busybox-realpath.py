#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

EXPECTED = {
    Path("crates/uv-install-wheel/src/wheel.rs"): {"realpath --": 2, "dirname --": 2},
    Path("crates/uv-virtualenv/src/virtualenv.rs"): {"realpath --": 2, "dirname --": 4},
    Path("crates/uv/src/commands/project/run.rs"): {"realpath --": 1, "dirname --": 1},
}

VIRTUALENV_UNFORMATTED = '''            (true, "activate") => Cow::Borrowed(
                r#"'"$(dirname "$(dirname "$(realpath "$SCRIPT_PATH")")")"'"#,
            ),'''
VIRTUALENV_FORMATTED = '''            (true, "activate") => {
                Cow::Borrowed(r#"'"$(dirname "$(dirname "$(realpath "$SCRIPT_PATH")")")"'"#)
            }'''

totals = {"realpath --": 0, "dirname --": 0}

for path, expected in EXPECTED.items():
    text = path.read_text()
    counts = {needle: text.count(needle) for needle in totals}
    if counts != expected:
        raise SystemExit(f"unexpected delimiter counts in {path}: {counts} != {expected}")

    updated = text.replace("realpath --", "realpath").replace("dirname --", "dirname")
    if path.name == "virtualenv.rs":
        if updated.count(VIRTUALENV_UNFORMATTED) != 1:
            raise SystemExit("unexpected relocatable activate arm after delimiter replacement")
        updated = updated.replace(VIRTUALENV_UNFORMATTED, VIRTUALENV_FORMATTED)

    if updated == text:
        raise SystemExit(f"candidate made no change in {path}")
    if "realpath --" in updated or "dirname --" in updated:
        raise SystemExit(f"launcher delimiter remains in {path}")

    path.write_text(updated)
    for needle, count in counts.items():
        totals[needle] += count
    print(f"{path}: realpath={counts['realpath --']} dirname={counts['dirname --']}")

if totals != {"realpath --": 5, "dirname --": 7}:
    raise SystemExit(f"unexpected candidate totals: {totals}")

print(f"UNIT_02_PATCH=realpath:{totals['realpath --']},dirname:{totals['dirname --']}")
