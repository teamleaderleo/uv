#!/usr/bin/env python3
"""Attach trusted extracted-member receipts to every wheel archive publisher."""

from __future__ import annotations

from pathlib import Path
import re
import sys


path = Path(sys.argv[1]) / "crates/uv-distribution/src/distribution_database.rs"
text = path.read_text(encoding="utf-8")


def replace_exact(old: str, new: str, *, name: str, count: int = 1) -> None:
    global text
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{name} mismatch: expected {count}, found {actual}")
    text = text.replace(old, new)


replace_exact(
    "use std::path::Path;\n",
    "use std::path::{Path, PathBuf};\n",
    name="Path import",
)
replace_exact(
    "use uv_install_wheel::validate_and_heal_record;\n",
    "use uv_install_wheel::validate_and_heal_record_with_manifest;\n",
    name="RECORD helper import",
)

# Four independent extraction paths validate RECORD before publishing an archive:
# streamed HTTP, downloaded HTTP, local path/Git, and the shared unzip helper.
validation_pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)validate_and_heal_record\("
    r"\s*temp_dir\.path\(\),\s*files\.iter\(\),\s*dist\s*\)"
    r"\s*\.map_err\(Error::InstallWheelError\)\?;"
)


def validation_replacement(match: re.Match[str]) -> str:
    indent = match.group("indent")
    continuation = indent + "    "
    return (
        f"{indent}let members = validate_and_heal_record_with_manifest(\n"
        f"{continuation}temp_dir.path(),\n"
        f"{continuation}files.iter(),\n"
        f"{continuation}dist,\n"
        f"{indent})\n"
        f"{continuation}.map_err(Error::InstallWheelError)?;"
    )


text, validation_count = validation_pattern.subn(validation_replacement, text)
if validation_count != 4:
    raise SystemExit(
        f"RECORD validation call mismatch: expected 4, found {validation_count}"
    )

# The streamed and downloaded HTTP publishers have the same Archive::new tail.
replace_exact(
    "                    filename.clone(),\n"
    "                    Some(actual_size),\n"
    "                ))\n",
    "                    filename.clone(),\n"
    "                    Some(actual_size),\n"
    "                    members,\n"
    "                ))\n",
    name="HTTP archive constructors",
    count=2,
)

# The no-hash local path reuses the shared unzip helper; return its member receipt
# with the archive ID instead of discarding it.
replace_exact(
    "            let archive = Archive::new(\n"
    "                self.unzip_wheel(path, wheel_entry.path(), DistRef::Built(dist))\n"
    "                    .await?,\n"
    "                HashDigests::empty(),\n"
    "                filename.clone(),\n"
    "                None,\n"
    "            );\n",
    "            let (id, members) = self\n"
    "                .unzip_wheel(path, wheel_entry.path(), DistRef::Built(dist))\n"
    "                .await?;\n"
    "            let archive = Archive::new(\n"
    "                id,\n"
    "                HashDigests::empty(),\n"
    "                filename.clone(),\n"
    "                None,\n"
    "                members,\n"
    "            );\n",
    name="shared unzip archive constructor",
)

# The hashed local path performs extraction inline and already owns `members`.
replace_exact(
    "            let archive = Archive::new(id, hashes, filename.clone(), None);\n",
    "            let archive = Archive::new(id, hashes, filename.clone(), None, members);\n",
    name="hashed local archive constructor",
)

replace_exact(
    "    ) -> Result<ArchiveId, Error> {\n",
    "    ) -> Result<(ArchiveId, Vec<(PathBuf, u64)>), Error> {\n",
    name="unzip helper return type",
)
replace_exact(
    "        Ok(id)\n"
    "    }\n\n"
    "    /// Returns a GET [`reqwest::Request`] for the given URL.\n",
    "        Ok((id, members))\n"
    "    }\n\n"
    "    /// Returns a GET [`reqwest::Request`] for the given URL.\n",
    name="unzip helper return value",
)

path.write_text(text, encoding="utf-8")
print(path)
