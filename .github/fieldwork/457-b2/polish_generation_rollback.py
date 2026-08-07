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

# Serialize only the live generation commit. Downloading and staging may remain concurrent.
old_import = "use uv_fs::Simplified;\n"
new_import = "#[cfg(windows)]\nuse uv_fs::{LockedFile, LockedFileMode};\nuse uv_fs::Simplified;\n"
if text.count(old_import) != 1:
    raise SystemExit(f"expected one uv_fs import, found {text.count(old_import)}")
text = text.replace(old_import, new_import, 1)

old_commit = '''    #[cfg(windows)]
    replace_from_temporary_install(
        temporary_install_dir.path(),
        temporary_config_dir.path(),
        &receipt_path,
        &install_prefix,
        modify_path,
    )?;
'''
new_commit = '''    #[cfg(windows)]
    let _update_lock = acquire_windows_update_lock(&install_prefix).await?;
    #[cfg(windows)]
    replace_from_temporary_install(
        temporary_install_dir.path(),
        temporary_config_dir.path(),
        &receipt_path,
        &install_prefix,
        modify_path,
    )?;
'''
if text.count(old_commit) != 1:
    raise SystemExit(f"expected one Windows live commit block, found {text.count(old_commit)}")
text = text.replace(old_commit, new_commit, 1)

lock_helper_anchor = "#[cfg(windows)]\nfn replace_from_temporary_install("
lock_helper = '''#[cfg(windows)]
async fn acquire_windows_update_lock(install_prefix: &Path) -> Result<LockedFile> {
    Ok(LockedFile::acquire(
        install_prefix.join(".uv-self-update.lock"),
        LockedFileMode::Exclusive,
        install_prefix.user_display(),
    )
    .await?)
}

#[cfg(windows)]
fn replace_from_temporary_install('''
if text.count(lock_helper_anchor) != 1:
    raise SystemExit(
        f"expected one replacement-helper anchor, found {text.count(lock_helper_anchor)}"
    )
text = text.replace(lock_helper_anchor, lock_helper, 1)

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

# Windows path lookup is ordinarily case-insensitive, while OsString/Path equality is not.
# Excluding the running executable by staged filename spelling can therefore classify `uv.exe`
# as a companion when the live process path is spelled `UV.EXE`. Compare the destination's live
# filesystem identity with the current executable instead. Non-existent companion destinations
# simply fail canonicalization and remain companions.
old_companions = '''    let companions = entries
        .into_iter()
        .filter(|entry| entry.file_name() != current_file_name)
        .map(|entry| {
            let destination = install_dir.join(entry.file_name());
            (entry.path(), destination)
        })
        .collect::<Vec<_>>();
'''
new_companions = '''    let current_executable_canonical = dunce::canonicalize(current_executable)
        .unwrap_or_else(|_| current_executable.to_path_buf());
    let companions = entries
        .into_iter()
        .filter_map(|entry| {
            let destination = install_dir.join(entry.file_name());
            if dunce::canonicalize(&destination)
                .is_ok_and(|destination| destination == current_executable_canonical)
            {
                None
            } else {
                Some((entry.path(), destination))
            }
        })
        .collect::<Vec<_>>();
'''
if text.count(old_companions) != 1:
    raise SystemExit(
        f"expected one companion-selection block, found {text.count(old_companions)}"
    )
text = text.replace(old_companions, new_companions, 1)

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

    #[cfg(windows)]
    #[test]
    fn fieldwork_current_head_generation_rollback_excludes_case_varied_current_executable(
    ) -> Result<()> {
        let temp_dir = TempDir::new()?;
        let staged_dir = temp_dir.path().join("staged");
        let live_dir = temp_dir.path().join("live");
        let staged_config_dir = temp_dir.path().join("staged-config");
        let staged_receipt_dir = staged_config_dir.join("uv");
        fs_err::create_dir_all(&staged_dir)?;
        fs_err::create_dir_all(&live_dir)?;
        fs_err::create_dir_all(&staged_receipt_dir)?;

        // Use a different spelling from the staged payload. On ordinary Windows filesystems,
        // these names identify the same live file despite not being equal Rust paths.
        let live_uv = live_dir.join("UV.EXE");
        let live_uvx = live_dir.join("uvx.exe");
        let receipt_path = temp_dir.path().join("uv-receipt.json");
        fs_err::write(&live_uv, b"old-uv")?;
        fs_err::write(&live_uvx, b"old-uvx")?;
        fs_err::write(staged_dir.join("uv.exe"), b"new-uv")?;
        fs_err::write(staged_dir.join("uvx.exe"), b"new-uvx")?;
        fs_err::write(
            staged_receipt_dir.join("uv-receipt.json"),
            serde_json::to_vec(&serde_json::json!({
                "binaries": ["uv", "uvx"],
                "install_prefix": staged_dir,
                "modify_path": false,
                "version": "0.12.1"
            }))?,
        )?;
        fs_err::write(
            &receipt_path,
            serde_json::to_vec(&serde_json::json!({
                "binaries": ["uv", "uvx"],
                "install_prefix": live_dir,
                "modify_path": true,
                "version": "0.12.0"
            }))?,
        )?;

        replace_from_temporary_install_with(
            &staged_dir,
            &staged_config_dir,
            &receipt_path,
            &live_dir,
            true,
            &live_uv,
            |replacement| {
                assert_eq!(replacement, staged_dir.join("uv.exe"));
                assert_eq!(
                    fs_err::read(&live_uv)?,
                    b"old-uv",
                    "case-varied current executable was copied as a companion before finalization"
                );
                fs_err::write(&live_uv, b"new-uv")?;
                Ok(())
            },
        )?;

        assert_eq!(fs_err::read(&live_uv)?, b"new-uv");
        assert_eq!(fs_err::read(&live_uvx)?, b"new-uvx");
        Ok(())
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn fieldwork_current_head_generation_rollback_serializes_live_update_window() -> Result<()>
    {
        let install_dir = TempDir::new()?;
        let first = acquire_windows_update_lock(install_dir.path()).await?;

        let blocked = tokio::time::timeout(
            Duration::from_millis(100),
            acquire_windows_update_lock(install_dir.path()),
        )
        .await;
        assert!(
            blocked.is_err(),
            "a second updater acquired the live-generation lock before the first released it"
        );

        drop(first);
        let second = tokio::time::timeout(
            Duration::from_secs(2),
            acquire_windows_update_lock(install_dir.path()),
        )
        .await
        .context("second updater did not acquire the lock after release")??;
        drop(second);
        Ok(())
    }
'''

module_end = text.rfind("\n}")
if module_end < 0:
    raise SystemExit("test module closing brace not found")
text = text[:module_end] + running_snapshot_test + text[module_end:]
path.write_text(text, encoding="utf-8")
