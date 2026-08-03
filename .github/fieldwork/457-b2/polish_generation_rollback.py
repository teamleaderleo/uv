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

mid_copy_start = text.index(
    "fn fieldwork_current_head_generation_rollback_restores_mid_copy_failure()"
)
mid_copy_end = text.index(
    "fn fieldwork_current_head_generation_rollback_commits_successful_generation()",
    mid_copy_start,
)
mid_copy = text[mid_copy_start:mid_copy_end]
for old, new in {
    'let live_uvw = live_dir.join("uvw.exe");': 'let live_uvz = live_dir.join("uvz.exe");',
    'assert!(!live_uvw.exists());': 'assert!(!live_uvz.exists());',
}.items():
    count = mid_copy.count(old)
    if count != 1:
        raise SystemExit(f"expected one mid-copy occurrence of {old!r}, found {count}")
    mid_copy = mid_copy.replace(old, new, 1)

text = text[:mid_copy_start] + mid_copy + text[mid_copy_end:]

running_snapshot_test = r'''

    #[cfg(windows)]
    #[test]
    fn fieldwork_current_head_generation_rollback_can_snapshot_running_executable() -> Result<()> {
        let rollback_dir = TempDir::new()?;
        let current_executable = std::env::current_exe()?;
        let snapshot = WindowsUpdateSnapshot::capture(
            &current_executable,
            rollback_dir.path(),
            0,
        )?;
        let backup = snapshot
            .backup
            .as_deref()
            .context("running executable snapshot should have backup bytes")?;
        assert!(backup.is_file());
        assert!(files_are_equal(&current_executable, backup)?);
        Ok(())
    }
'''

module_end = text.rfind("\n}")
if module_end < 0:
    raise SystemExit("test module closing brace not found")
text = text[:module_end] + running_snapshot_test + text[module_end:]
path.write_text(text, encoding="utf-8")
