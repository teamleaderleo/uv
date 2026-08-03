from pathlib import Path

path = Path("crates/uv/src/commands/self_update.rs")
text = path.read_text(encoding="utf-8")

replacements = {
    "entries.sort_by_key(std::fs::DirEntry::file_name);": "entries.sort_by_key(|entry| entry.file_name());",
    "fs_err::create_dir(staged_dir.join(\"uvw.exe\"))?;\n        fs_err::write(\n            staged_receipt_dir.join(\"uv-receipt.json\"),": "fs_err::create_dir(staged_dir.join(\"uvz.exe\"))?;\n        fs_err::write(\n            staged_receipt_dir.join(\"uv-receipt.json\"),",
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one occurrence of {old!r}, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
