#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-install-wheel/src/lib.rs"
text = path.read_text()
old = "pub use wheel::{WheelFile, read_record, read_record_into_iter, validate_and_heal_record};\n"
new = (
    "pub use wheel::{\n"
    "    WheelFile, read_record, read_record_into_iter, validate_and_heal_record,\n"
    "    validate_and_heal_record_with_manifest,\n"
    "};\n"
)
if text.count(old) != 1:
    raise SystemExit("manifest export fragment mismatch")
path.write_text(text.replace(old, new))
