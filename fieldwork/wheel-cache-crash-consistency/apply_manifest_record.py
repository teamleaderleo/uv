#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-install-wheel/src/wheel.rs"
text = path.read_text()

def replace(old: str, new: str) -> None:
    global text
    if text.count(old) != 1:
        raise SystemExit(f"record fragment mismatch: {old[:100]!r}")
    text = text.replace(old, new)

replace(
    "pub fn validate_and_heal_record<'a>(\n"
    "    wheel_dir: &Path,\n"
    "    unpacked_wheel: impl IntoIterator<Item = &'a (PathBuf, u64)>,\n"
    "    dist: impl Display,\n"
    ") -> Result<(), Error> {\n"
    "    // On the filesystem: The unpacked files of the wheel.\n"
    "    let mut files: BTreeMap<&Path, u64> = unpacked_wheel\n"
    "        .into_iter()\n"
    "        .map(|(path, size)| (path.as_path(), *size))\n"
    "        .collect();\n",
    "pub fn validate_and_heal_record<'a>(\n"
    "    wheel_dir: &Path,\n"
    "    unpacked_wheel: impl IntoIterator<Item = &'a (PathBuf, u64)>,\n"
    "    dist: impl Display,\n"
    ") -> Result<(), Error> {\n"
    "    validate_and_heal_record_with_manifest(wheel_dir, unpacked_wheel, dist).map(drop)\n"
    "}\n\n"
    "/// Validate and heal RECORD while returning a trusted extracted-member inventory.\n"
    "pub fn validate_and_heal_record_with_manifest<'a>(\n"
    "    wheel_dir: &Path,\n"
    "    unpacked_wheel: impl IntoIterator<Item = &'a (PathBuf, u64)>,\n"
    "    dist: impl Display,\n"
    ") -> Result<Vec<(PathBuf, u64)>, Error> {\n"
    "    let mut unpacked_files: BTreeMap<PathBuf, u64> = unpacked_wheel\n"
    "        .into_iter()\n"
    "        .map(|(path, size)| (path.clone(), *size))\n"
    "        .collect();\n\n"
    "    // On the filesystem: The unpacked files of the wheel.\n"
    "    let mut files: BTreeMap<&Path, u64> = unpacked_files\n"
    "        .iter()\n"
    "        .map(|(path, size)| (path.as_path(), *size))\n"
    "        .collect();\n",
)
replace(
    "        write_record(wheel_dir, &dist_info_prefix, record)?;\n"
    "    }\n\n"
    "    Ok(())\n"
    "}\n",
    "        write_record(wheel_dir, &dist_info_prefix, record)?;\n"
    "    }\n\n"
    "    let record_relative = PathBuf::from(&dist_info_dir).join(\"RECORD\");\n"
    "    unpacked_files.insert(record_relative, fs::metadata(&record_path)?.len());\n"
    "    Ok(unpacked_files.into_iter().collect())\n"
    "}\n",
)
path.write_text(text)
