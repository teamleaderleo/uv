#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-distribution/src/distribution_database.rs"
text = path.read_text()

def replace(old: str, new: str, count: int = 1) -> None:
    global text
    if text.count(old) != count:
        raise SystemExit(f"database fragment mismatch: {old[:100]!r}")
    text = text.replace(old, new)

replace("use std::path::Path;\n", "use std::path::{Path, PathBuf};\n")
replace(
    "use uv_install_wheel::validate_and_heal_record;\n",
    "use uv_install_wheel::validate_and_heal_record_with_manifest;\n",
)
replace(
    "                validate_and_heal_record(temp_dir.path(), files.iter(), dist)\n"
    "                    .map_err(Error::InstallWheelError)?;\n",
    "                let members = validate_and_heal_record_with_manifest(\n"
    "                    temp_dir.path(),\n"
    "                    files.iter(),\n"
    "                    dist,\n"
    "                )\n"
    "                .map_err(Error::InstallWheelError)?;\n",
    3,
)
replace(
    "        validate_and_heal_record(temp_dir.path(), files.iter(), dist)\n"
    "            .map_err(Error::InstallWheelError)?;\n",
    "        let members =\n"
    "            validate_and_heal_record_with_manifest(temp_dir.path(), files.iter(), dist)\n"
    "                .map_err(Error::InstallWheelError)?;\n",
)
replace(
    "                    filename.clone(),\n"
    "                    Some(actual_size),\n"
    "                ))\n",
    "                    filename.clone(),\n"
    "                    Some(actual_size),\n"
    "                    members,\n"
    "                ))\n",
    2,
)
replace(
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
)
replace(
    "            let archive = Archive::new(id, hashes, filename.clone(), None);\n",
    "            let archive = Archive::new(id, hashes, filename.clone(), None, members);\n",
)
replace(
    "    ) -> Result<ArchiveId, Error> {\n",
    "    ) -> Result<(ArchiveId, Vec<(PathBuf, u64)>), Error> {\n",
)
replace(
    "        Ok(id)\n"
    "    }\n\n"
    "    /// Returns a GET [`reqwest::Request`] for the given URL.\n",
    "        Ok((id, members))\n"
    "    }\n\n"
    "    /// Returns a GET [`reqwest::Request`] for the given URL.\n",
)
path.write_text(text)
