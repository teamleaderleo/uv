use std::ffi::OsStr;
use std::fs::{self, File};
use std::io::{self, Write};
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};
use std::path::{Path, PathBuf};

use windows::Win32::Foundation::{HANDLE, WAIT_OBJECT_0};
use windows::Win32::System::Threading::{
    INFINITE, OpenProcess, PROCESS_SYNCHRONIZE, WaitForSingleObject,
};

/// Options used by the experimental deferred update finalizer.
#[derive(Debug, Clone, Copy, Default)]
pub struct UpdateFinalizeOptions {
    /// Inject an ordinary failure after the old canonical file has moved to its backup.
    ///
    /// This is used only by the Fieldwork executable to prove rollback behavior.
    pub fail_after_backup: bool,
}

/// Stage a replacement next to the canonical file, wait for the parent process to exit,
/// then commit the replacement with an explicit backup and ordinary-error rollback.
///
/// The important ordering guarantee is that parent-process authority is acquired before the
/// potentially slow copy, and all validation and copying happen before the canonical file is
/// touched. The remaining commit section contains only same-directory renames. A small journal
/// records enough information for a future recovery pass if the machine loses power between those
/// renames.
pub fn finalize_update_after_process_exit(
    parent_process_id: u32,
    canonical: &Path,
    replacement: &Path,
    options: UpdateFinalizeOptions,
) -> io::Result<()> {
    ensure_regular_file(canonical, "canonical executable")?;
    ensure_regular_file(replacement, "staged replacement")?;

    // Acquire a synchronization handle before any slow staging work. The handle continues to
    // identify the original process object if the parent exits while the replacement is copied;
    // reopening by PID afterward would introduce an exit/PID-reuse race.
    let parent_process = open_process_for_wait(parent_process_id)?;

    let parent = canonical.parent().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "canonical executable has no parent directory",
        )
    })?;
    let file_name = canonical.file_name().and_then(OsStr::to_str).ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "canonical executable filename is not valid Unicode",
        )
    })?;

    let suffix = format!("{}.{}", parent_process_id, std::process::id());
    let staged = parent.join(format!(".{file_name}.update-stage.{suffix}"));
    let backup = parent.join(format!(".{file_name}.update-backup.{suffix}"));
    let journal = parent.join(format!(".{file_name}.update-journal.{suffix}"));

    remove_if_exists(&staged)?;
    remove_if_exists(&backup)?;
    remove_if_exists(&journal)?;

    // This is the only potentially cross-filesystem or long-running file transfer. It happens
    // while the old canonical executable is still present and runnable.
    fs::copy(replacement, &staged)?;
    sync_file(&staged)?;
    write_journal(&journal, canonical, &staged, &backup)?;

    wait_for_process_exit(&parent_process, parent_process_id)?;

    fs::rename(canonical, &backup)?;

    if options.fail_after_backup {
        rollback_backup(canonical, &backup)?;
        remove_if_exists(&staged)?;
        remove_if_exists(&journal)?;
        return Err(io::Error::other(
            "injected failure after canonical backup",
        ));
    }

    if let Err(error) = fs::rename(&staged, canonical) {
        let rollback_error = rollback_backup(canonical, &backup).err();
        remove_if_exists(&staged).ok();
        remove_if_exists(&journal).ok();
        return match rollback_error {
            Some(rollback_error) => Err(io::Error::other(format!(
                "failed to commit replacement: {error}; rollback also failed: {rollback_error}"
            ))),
            None => Err(error),
        };
    }

    remove_if_exists(&backup)?;
    remove_if_exists(&journal)?;
    Ok(())
}

fn ensure_regular_file(path: &Path, description: &str) -> io::Result<()> {
    let metadata = fs::metadata(path).map_err(|error| {
        io::Error::new(
            error.kind(),
            format!("failed to inspect {description} at `{}`: {error}", path.display()),
        )
    })?;
    if !metadata.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("{description} at `{}` is not a file", path.display()),
        ));
    }
    Ok(())
}

fn sync_file(path: &Path) -> io::Result<()> {
    File::open(path)?.sync_all()
}

fn write_journal(
    journal: &Path,
    canonical: &Path,
    staged: &Path,
    backup: &Path,
) -> io::Result<()> {
    let mut file = File::create(journal)?;
    writeln!(file, "canonical={}", canonical.display())?;
    writeln!(file, "staged={}", staged.display())?;
    writeln!(file, "backup={}", backup.display())?;
    file.sync_all()
}

fn rollback_backup(canonical: &Path, backup: &Path) -> io::Result<()> {
    if canonical.exists() {
        fs::remove_file(canonical)?;
    }
    fs::rename(backup, canonical)
}

fn remove_if_exists(path: &Path) -> io::Result<()> {
    match fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error),
    }
}

fn open_process_for_wait(process_id: u32) -> io::Result<OwnedHandle> {
    #[allow(unsafe_code)]
    let handle = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, false, process_id) }
        .map_err(|error| io::Error::other(error.to_string()))?;

    #[allow(unsafe_code)]
    Ok(unsafe { OwnedHandle::from_raw_handle(handle.0) })
}

fn wait_for_process_exit(handle: &OwnedHandle, process_id: u32) -> io::Result<()> {
    #[allow(unsafe_code)]
    let wait_result = unsafe { WaitForSingleObject(HANDLE(handle.as_raw_handle()), INFINITE) };
    if wait_result != WAIT_OBJECT_0 {
        return Err(io::Error::other(format!(
            "waiting for parent process {process_id} returned {wait_result:?}"
        )));
    }
    Ok(())
}

#[allow(dead_code)]
fn _assert_paths_are_owned(_: PathBuf) {}
