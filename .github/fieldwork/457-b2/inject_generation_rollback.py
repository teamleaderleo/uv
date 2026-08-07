from pathlib import Path

path = Path("crates/uv/src/commands/self_update.rs")
text = path.read_text(encoding="utf-8")

start_marker = "#[cfg(windows)]\nfn replace_from_temporary_install("
end_marker = "/// Promote the receipt written by a staged Windows installation to its original location."

if text.count(start_marker) != 1:
    raise SystemExit(f"expected exactly one replacement helper, found {text.count(start_marker)}")
start = text.index(start_marker)
end = text.index(end_marker, start)

replacement = r'''#[cfg(windows)]
#[derive(Debug)]
struct WindowsUpdateSnapshot {
    path: PathBuf,
    backup: Option<PathBuf>,
}

#[cfg(windows)]
impl WindowsUpdateSnapshot {
    fn capture(path: &Path, backup_dir: &Path, index: usize) -> Result<Self> {
        let backup = if path.exists() {
            let backup = backup_dir.join(format!("{index}.bak"));
            fs_err::copy(path, &backup).with_context(|| {
                format!(
                    "Failed to snapshot live update file `{}`",
                    path.display()
                )
            })?;
            Some(backup)
        } else {
            None
        };
        Ok(Self {
            path: path.to_path_buf(),
            backup,
        })
    }

    fn restore(&self) -> Result<()> {
        match self.backup.as_deref() {
            Some(backup) => {
                if self.path.exists() && files_are_equal(&self.path, backup)? {
                    return Ok(());
                }
                if self.path.exists() {
                    fs_err::remove_file(&self.path).with_context(|| {
                        format!(
                            "Failed to remove partially updated file `{}` during rollback",
                            self.path.display()
                        )
                    })?;
                }
                fs_err::copy(backup, &self.path).with_context(|| {
                    format!(
                        "Failed to restore update snapshot `{}` to `{}`",
                        backup.display(),
                        self.path.display()
                    )
                })?;
            }
            None => {
                if self.path.exists() {
                    fs_err::remove_file(&self.path).with_context(|| {
                        format!(
                            "Failed to remove newly created update file `{}` during rollback",
                            self.path.display()
                        )
                    })?;
                }
            }
        }
        Ok(())
    }
}

#[cfg(windows)]
fn files_are_equal(left: &Path, right: &Path) -> Result<bool> {
    if fs_err::metadata(left)?.len() != fs_err::metadata(right)?.len() {
        return Ok(false);
    }

    let mut left = std::io::BufReader::new(std::fs::File::open(left)?);
    let mut right = std::io::BufReader::new(std::fs::File::open(right)?);
    let mut left_buffer = [0_u8; 64 * 1024];
    let mut right_buffer = [0_u8; 64 * 1024];

    loop {
        let left_read = std::io::Read::read(&mut left, &mut left_buffer)?;
        let right_read = std::io::Read::read(&mut right, &mut right_buffer)?;
        if left_read != right_read || left_buffer[..left_read] != right_buffer[..right_read] {
            return Ok(false);
        }
        if left_read == 0 {
            return Ok(true);
        }
    }
}

#[cfg(windows)]
fn rollback_windows_update(snapshots: &[WindowsUpdateSnapshot]) -> Result<()> {
    let mut failures = Vec::new();
    for snapshot in snapshots {
        if let Err(error) = snapshot.restore() {
            failures.push(format!("`{}`: {error:#}", snapshot.path.display()));
        }
    }

    if failures.is_empty() {
        Ok(())
    } else {
        Err(anyhow::anyhow!(
            "Failed to restore one or more update files: {}",
            failures.join("; ")
        ))
    }
}

#[cfg(windows)]
fn replace_from_temporary_install(
    temporary_install_dir: &Path,
    temporary_config_dir: &Path,
    receipt_path: &Path,
    install_prefix: &Path,
    modify_path: bool,
) -> Result<()> {
    let current_executable = std::env::current_exe()?;
    replace_from_temporary_install_with(
        temporary_install_dir,
        temporary_config_dir,
        receipt_path,
        install_prefix,
        modify_path,
        &current_executable,
        |replacement| {
            self_replace::self_replace(replacement)
                .context("Failed to replace the current executable")?;
            Ok(())
        },
    )
}

#[cfg(windows)]
fn replace_from_temporary_install_with<F>(
    temporary_install_dir: &Path,
    temporary_config_dir: &Path,
    receipt_path: &Path,
    install_prefix: &Path,
    modify_path: bool,
    current_executable: &Path,
    finalize_current_executable: F,
) -> Result<()>
where
    F: FnOnce(&Path) -> Result<()>,
{
    let current_file_name = current_executable.file_name().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "Current executable has no file name",
        )
    })?;
    let install_dir = current_executable.parent().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "Current executable has no parent directory",
        )
    })?;

    let rollback_dir = tempfile::Builder::new()
        .prefix(".uv-update-rollback-")
        .tempdir_in(install_dir)
        .context("Failed to create update rollback directory")?;

    let mut entries = fs_err::read_dir(temporary_install_dir)?
        .collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(std::fs::DirEntry::file_name);

    let companions = entries
        .into_iter()
        .filter(|entry| entry.file_name() != current_file_name)
        .map(|entry| {
            let destination = install_dir.join(entry.file_name());
            (entry.path(), destination)
        })
        .collect::<Vec<_>>();

    // Capture every live path before the first mutation. The canonical executable snapshot is
    // intentionally independent of self-replace's private temporary file so an ordinary
    // post-rename error can restore the command at its canonical path.
    let mut snapshots = Vec::with_capacity(companions.len() + 2);
    snapshots.push(WindowsUpdateSnapshot::capture(
        current_executable,
        rollback_dir.path(),
        0,
    )?);
    for (index, (_, destination)) in companions.iter().enumerate() {
        snapshots.push(WindowsUpdateSnapshot::capture(
            destination,
            rollback_dir.path(),
            index + 1,
        )?);
    }
    snapshots.push(WindowsUpdateSnapshot::capture(
        receipt_path,
        rollback_dir.path(),
        companions.len() + 1,
    )?);

    let update = (|| -> Result<()> {
        for (source, destination) in &companions {
            fs_err::copy(source, destination).with_context(|| {
                format!(
                    "Failed to copy staged companion `{}` to `{}`",
                    source.display(),
                    destination.display()
                )
            })?;
        }

        update_standalone_install_receipt(
            temporary_config_dir,
            receipt_path,
            install_prefix,
            modify_path,
        )?;

        finalize_current_executable(&temporary_install_dir.join(current_file_name))?;
        Ok(())
    })();

    if let Err(error) = update {
        if let Err(rollback_error) = rollback_windows_update(&snapshots) {
            let retained = rollback_dir.path().to_path_buf();
            std::mem::forget(rollback_dir);
            return Err(error.context(format!(
                "Update rollback also failed: {rollback_error:#}. Snapshots retained at `{}`",
                retained.display()
            )));
        }
        return Err(error);
    }

    Ok(())
}

'''

text = text[:start] + replacement + text[end:]

tests = r'''

    #[cfg(windows)]
    #[test]
    fn fieldwork_current_head_generation_rollback_restores_all_live_state_after_finalizer_error(
    ) -> Result<()> {
        let temp_dir = TempDir::new()?;
        let staged_dir = temp_dir.path().join("staged");
        let live_dir = temp_dir.path().join("live");
        let staged_config_dir = temp_dir.path().join("staged-config");
        let staged_receipt_dir = staged_config_dir.join("uv");
        fs_err::create_dir_all(&staged_dir)?;
        fs_err::create_dir_all(&live_dir)?;
        fs_err::create_dir_all(&staged_receipt_dir)?;

        let live_uv = live_dir.join("uv.exe");
        let live_uvx = live_dir.join("uvx.exe");
        let live_uvw = live_dir.join("uvw.exe");
        let receipt_path = temp_dir.path().join("uv-receipt.json");
        fs_err::write(&live_uv, b"old-uv")?;
        fs_err::write(&live_uvx, b"old-uvx")?;
        fs_err::write(staged_dir.join("uv.exe"), b"new-uv")?;
        fs_err::write(staged_dir.join("uvx.exe"), b"new-uvx")?;
        fs_err::write(staged_dir.join("uvw.exe"), b"new-uvw")?;
        fs_err::write(
            staged_receipt_dir.join("uv-receipt.json"),
            serde_json::to_vec(&serde_json::json!({
                "binaries": ["uv", "uvx", "uvw"],
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

        let error = replace_from_temporary_install_with(
            &staged_dir,
            &staged_config_dir,
            &receipt_path,
            &live_dir,
            true,
            &live_uv,
            |_| {
                fs_err::remove_file(&live_uv)?;
                anyhow::bail!("injected destructive finalizer failure")
            },
        )
        .expect_err("finalizer failure should be returned after rollback");

        assert!(
            error
                .to_string()
                .contains("injected destructive finalizer failure")
        );
        assert_eq!(fs_err::read(&live_uv)?, b"old-uv");
        assert_eq!(fs_err::read(&live_uvx)?, b"old-uvx");
        assert!(!live_uvw.exists());
        let receipt: Value = serde_json::from_slice(&fs_err::read(&receipt_path)?)?;
        assert_eq!(receipt["version"], Value::String("0.12.0".to_string()));
        assert_eq!(receipt["modify_path"], Value::Bool(true));
        assert!(
            fs_err::read_dir(&live_dir)?.all(|entry| {
                !entry
                    .expect("live directory entry")
                    .file_name()
                    .to_string_lossy()
                    .starts_with(".uv-update-rollback-")
            }),
            "successful rollback should clean its snapshot directory"
        );
        Ok(())
    }

    #[cfg(windows)]
    #[test]
    fn fieldwork_current_head_generation_rollback_restores_mid_copy_failure() -> Result<()> {
        let temp_dir = TempDir::new()?;
        let staged_dir = temp_dir.path().join("staged");
        let live_dir = temp_dir.path().join("live");
        let staged_config_dir = temp_dir.path().join("staged-config");
        let staged_receipt_dir = staged_config_dir.join("uv");
        fs_err::create_dir_all(&staged_dir)?;
        fs_err::create_dir_all(&live_dir)?;
        fs_err::create_dir_all(&staged_receipt_dir)?;

        let live_uv = live_dir.join("uv.exe");
        let live_uvx = live_dir.join("uvx.exe");
        let live_uvw = live_dir.join("uvw.exe");
        let receipt_path = temp_dir.path().join("uv-receipt.json");
        fs_err::write(&live_uv, b"old-uv")?;
        fs_err::write(&live_uvx, b"old-uvx")?;
        fs_err::write(staged_dir.join("uv.exe"), b"new-uv")?;
        fs_err::write(staged_dir.join("uvx.exe"), b"new-uvx")?;
        fs_err::create_dir(staged_dir.join("uvw.exe"))?;
        fs_err::write(
            staged_receipt_dir.join("uv-receipt.json"),
            serde_json::to_vec(&serde_json::json!({"version": "0.12.1"}))?,
        )?;
        fs_err::write(
            &receipt_path,
            serde_json::to_vec(&serde_json::json!({
                "modify_path": true,
                "version": "0.12.0"
            }))?,
        )?;

        let finalizer_called = std::cell::Cell::new(false);
        replace_from_temporary_install_with(
            &staged_dir,
            &staged_config_dir,
            &receipt_path,
            &live_dir,
            true,
            &live_uv,
            |_| {
                finalizer_called.set(true);
                Ok(())
            },
        )
        .expect_err("copying a staged directory should fail and roll back prior copies");

        assert!(!finalizer_called.get());
        assert_eq!(fs_err::read(&live_uv)?, b"old-uv");
        assert_eq!(fs_err::read(&live_uvx)?, b"old-uvx");
        assert!(!live_uvw.exists());
        let receipt: Value = serde_json::from_slice(&fs_err::read(&receipt_path)?)?;
        assert_eq!(receipt["version"], Value::String("0.12.0".to_string()));
        Ok(())
    }

    #[cfg(windows)]
    #[test]
    fn fieldwork_current_head_generation_rollback_commits_successful_generation() -> Result<()> {
        let temp_dir = TempDir::new()?;
        let staged_dir = temp_dir.path().join("staged");
        let live_dir = temp_dir.path().join("live");
        let staged_config_dir = temp_dir.path().join("staged-config");
        let staged_receipt_dir = staged_config_dir.join("uv");
        fs_err::create_dir_all(&staged_dir)?;
        fs_err::create_dir_all(&live_dir)?;
        fs_err::create_dir_all(&staged_receipt_dir)?;

        let live_uv = live_dir.join("uv.exe");
        let live_uvx = live_dir.join("uvx.exe");
        let live_uvw = live_dir.join("uvw.exe");
        let receipt_path = temp_dir.path().join("uv-receipt.json");
        fs_err::write(&live_uv, b"old-uv")?;
        fs_err::write(&live_uvx, b"old-uvx")?;
        fs_err::write(staged_dir.join("uv.exe"), b"new-uv")?;
        fs_err::write(staged_dir.join("uvx.exe"), b"new-uvx")?;
        fs_err::write(staged_dir.join("uvw.exe"), b"new-uvw")?;
        fs_err::write(
            staged_receipt_dir.join("uv-receipt.json"),
            serde_json::to_vec(&serde_json::json!({
                "binaries": ["uv", "uvx", "uvw"],
                "install_prefix": staged_dir,
                "modify_path": false,
                "version": "0.12.1"
            }))?,
        )?;
        fs_err::write(
            &receipt_path,
            serde_json::to_vec(&serde_json::json!({
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
                fs_err::copy(replacement, &live_uv)?;
                Ok(())
            },
        )?;

        assert_eq!(fs_err::read(&live_uv)?, b"new-uv");
        assert_eq!(fs_err::read(&live_uvx)?, b"new-uvx");
        assert_eq!(fs_err::read(&live_uvw)?, b"new-uvw");
        let receipt: Value = serde_json::from_slice(&fs_err::read(&receipt_path)?)?;
        assert_eq!(receipt["version"], Value::String("0.12.1".to_string()));
        assert_eq!(receipt["modify_path"], Value::Bool(true));
        assert_eq!(
            receipt["install_prefix"],
            Value::String(live_dir.display().to_string())
        );
        Ok(())
    }
'''

module_end = text.rfind("\n}")
if module_end < 0:
    raise SystemExit("test module closing brace not found")
text = text[:module_end] + tests + text[module_end:]

path.write_text(text, encoding="utf-8")
