use std::ffi::OsStr;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};
use std::path::{Path, PathBuf};

use windows::Win32::Foundation::{HANDLE, WAIT_OBJECT_0};
use windows::Win32::System::Threading::{
    INFINITE, OpenProcess, PROCESS_SYNCHRONIZE, WaitForSingleObject,
};

/// Options used by the experimental deferred update finalizer.
#[derive(Debug, Clone, Default)]
pub struct UpdateFinalizeOptions {
    /// Inject an ordinary failure after the old canonical file has moved to its backup.
    ///
    /// This is used only by the Fieldwork executable to prove rollback behavior.
    pub fail_after_backup: bool,
    /// Inject rollback failure after the post-backup failure.
    ///
    /// The journal, staged replacement, and backup must remain available for a later recovery pass.
    pub fail_rollback_after_backup: bool,
    /// Optional marker written only after the finalizer owns a handle to the exact parent process.
    pub ready_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum UpdatePhase {
    Prepared,
    OldBackedUp,
    NewLive,
    Committed,
}

impl UpdatePhase {
    fn as_str(self) -> &'static str {
        match self {
            Self::Prepared => "prepared",
            Self::OldBackedUp => "old-backed-up",
            Self::NewLive => "new-live",
            Self::Committed => "committed",
        }
    }

    fn parse(value: &str) -> io::Result<Self> {
        match value {
            "prepared" => Ok(Self::Prepared),
            "old-backed-up" => Ok(Self::OldBackedUp),
            "new-live" => Ok(Self::NewLive),
            "committed" => Ok(Self::Committed),
            _ => Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("unknown update journal phase `{value}`"),
            )),
        }
    }
}

#[derive(Debug)]
struct UpdateJournal {
    canonical: PathBuf,
    staged: PathBuf,
    backup: PathBuf,
    phase: UpdatePhase,
}

/// Stage a replacement next to the canonical file, wait for the parent process to exit,
/// then commit the replacement with an explicit backup and recoverable phase journal.
pub fn finalize_update_after_process_exit(
    parent_process_id: u32,
    canonical: &Path,
    replacement: &Path,
    options: UpdateFinalizeOptions,
) -> io::Result<()> {
    ensure_regular_file(canonical, "canonical executable")?;
    ensure_regular_file(replacement, "staged replacement")?;

    // Acquire synchronization authority before slow staging. The owned handle continues to
    // identify the original process object even if its PID is later reused.
    let parent_process = open_process_for_wait(parent_process_id)?;
    if let Some(ready_path) = options.ready_path.as_deref() {
        write_ready_marker(ready_path, parent_process_id)?;
    }

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
    let journal_path = parent.join(format!(".{file_name}.update-journal.{suffix}"));
    let mut journal = UpdateJournal {
        canonical: canonical.to_path_buf(),
        staged,
        backup,
        phase: UpdatePhase::Prepared,
    };

    validate_journal_paths(&journal_path, &journal)?;
    remove_if_exists(&journal.staged)?;
    remove_if_exists(&journal.backup)?;
    remove_if_exists(&journal_path)?;

    // The only potentially long or cross-filesystem copy happens while canonical is untouched.
    fs::copy(replacement, &journal.staged)?;
    sync_file(&journal.staged)?;
    if let Err(error) = write_journal(&journal_path, &journal) {
        remove_if_exists(&journal.staged).ok();
        remove_if_exists(&journal_path).ok();
        return Err(error);
    }

    wait_for_process_exit(&parent_process, parent_process_id)?;

    fs::rename(&journal.canonical, &journal.backup)?;
    journal.phase = UpdatePhase::OldBackedUp;
    if let Err(error) = write_journal(&journal_path, &journal) {
        return rollback_after_error(&journal_path, &journal, error, false);
    }

    if options.fail_after_backup {
        return rollback_after_error(
            &journal_path,
            &journal,
            io::Error::other("injected failure after canonical backup"),
            options.fail_rollback_after_backup,
        );
    }

    if let Err(error) = fs::rename(&journal.staged, &journal.canonical) {
        return rollback_after_error(&journal_path, &journal, error, false);
    }

    journal.phase = UpdatePhase::NewLive;
    if let Err(error) = write_journal(&journal_path, &journal) {
        return rollback_after_error(&journal_path, &journal, error, false);
    }

    journal.phase = UpdatePhase::Committed;
    if let Err(error) = write_journal(&journal_path, &journal) {
        return rollback_after_error(&journal_path, &journal, error, false);
    }

    // Cleanup failures after the committed journal remain recoverable: the journal is removed last.
    remove_if_exists(&journal.backup)?;
    remove_if_exists(&journal.staged)?;
    remove_if_exists(&journal_path)?;
    Ok(())
}

/// Recover one interrupted update transaction from its phase journal.
///
/// Every non-committed phase conservatively chooses the old generation. A committed phase keeps
/// the new canonical file and removes transaction debris. Repeated recovery after cleanup is a
/// no-op.
pub fn recover_update_from_journal(journal_path: &Path) -> io::Result<()> {
    let journal = match read_journal(journal_path) {
        Ok(journal) => journal,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
        Err(error) => return Err(error),
    };
    validate_journal_paths(journal_path, &journal)?;

    match journal.phase {
        UpdatePhase::Committed => {
            ensure_regular_file(&journal.canonical, "committed canonical executable")?;
            remove_if_exists(&journal.backup)?;
            remove_if_exists(&journal.staged)?;
            remove_if_exists(journal_path)?;
        }
        UpdatePhase::Prepared | UpdatePhase::OldBackedUp | UpdatePhase::NewLive => {
            if journal.backup.exists() {
                if journal.canonical.exists() {
                    remove_if_exists(&journal.canonical)?;
                }
                fs::rename(&journal.backup, &journal.canonical)?;
            } else if !journal.canonical.exists() {
                return Err(io::Error::new(
                    io::ErrorKind::NotFound,
                    format!(
                        "uncommitted update has neither canonical nor backup file: `{}`",
                        journal_path.display()
                    ),
                ));
            }

            ensure_regular_file(&journal.canonical, "recovered canonical executable")?;
            remove_if_exists(&journal.staged)?;
            remove_if_exists(&journal.backup)?;
            remove_if_exists(journal_path)?;
        }
    }

    Ok(())
}

fn rollback_after_error(
    journal_path: &Path,
    journal: &UpdateJournal,
    source: io::Error,
    inject_rollback_failure: bool,
) -> io::Result<()> {
    if inject_rollback_failure {
        return Err(io::Error::other(format!(
            "update failed: {source}; rollback also failed: injected rollback failure; recovery journal preserved at `{}`",
            journal_path.display()
        )));
    }

    if let Err(rollback_error) = rollback_backup(&journal.canonical, &journal.backup) {
        return Err(io::Error::other(format!(
            "update failed: {source}; rollback also failed: {rollback_error}; recovery journal preserved at `{}`",
            journal_path.display()
        )));
    }

    // If cleanup after a successful rollback fails, preserve the journal. Its uncommitted phase and
    // restored canonical path let the next recovery pass finish removing stale transaction files.
    if let Err(cleanup_error) = remove_if_exists(&journal.staged) {
        return Err(io::Error::other(format!(
            "update failed: {source}; rollback restored canonical but stage cleanup failed: {cleanup_error}; recovery journal preserved at `{}`",
            journal_path.display()
        )));
    }
    if let Err(cleanup_error) = remove_if_exists(journal_path) {
        return Err(io::Error::other(format!(
            "update failed: {source}; rollback restored canonical but journal cleanup failed: {cleanup_error}; journal remains at `{}`",
            journal_path.display()
        )));
    }

    Err(source)
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

fn write_ready_marker(path: &Path, parent_process_id: u32) -> io::Result<()> {
    let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
    writeln!(file, "parent_process_id={parent_process_id}")?;
    writeln!(file, "finalizer_process_id={}", std::process::id())?;
    file.sync_all()
}

fn write_journal(path: &Path, journal: &UpdateJournal) -> io::Result<()> {
    let mut file = File::create(path)?;
    writeln!(file, "version=1")?;
    writeln!(file, "phase={}", journal.phase.as_str())?;
    writeln!(file, "canonical={}", journal.canonical.display())?;
    writeln!(file, "staged={}", journal.staged.display())?;
    writeln!(file, "backup={}", journal.backup.display())?;
    file.sync_all()
}

fn read_journal(path: &Path) -> io::Result<UpdateJournal> {
    let contents = fs::read_to_string(path)?;
    let mut version = None;
    let mut phase = None;
    let mut canonical = None;
    let mut staged = None;
    let mut backup = None;

    for line in contents.lines() {
        let (key, value) = line.split_once('=').ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("invalid update journal line `{line}`"),
            )
        })?;
        match key {
            "version" => version = Some(value),
            "phase" => phase = Some(UpdatePhase::parse(value)?),
            "canonical" => canonical = Some(PathBuf::from(value)),
            "staged" => staged = Some(PathBuf::from(value)),
            "backup" => backup = Some(PathBuf::from(value)),
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("unknown update journal field `{key}`"),
                ));
            }
        }
    }

    if version != Some("1") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unsupported or missing update journal version",
        ));
    }

    Ok(UpdateJournal {
        phase: phase.ok_or_else(|| missing_journal_field("phase"))?,
        canonical: canonical.ok_or_else(|| missing_journal_field("canonical"))?,
        staged: staged.ok_or_else(|| missing_journal_field("staged"))?,
        backup: backup.ok_or_else(|| missing_journal_field("backup"))?,
    })
}

fn missing_journal_field(field: &str) -> io::Error {
    io::Error::new(
        io::ErrorKind::InvalidData,
        format!("missing update journal field `{field}`"),
    )
}

fn validate_journal_paths(journal_path: &Path, journal: &UpdateJournal) -> io::Result<()> {
    let transaction_dir = journal_path.parent().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "update journal has no parent directory",
        )
    })?;

    for (name, path) in [
        ("canonical", &journal.canonical),
        ("staged", &journal.staged),
        ("backup", &journal.backup),
    ] {
        if path.parent() != Some(transaction_dir) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!(
                    "update journal {name} path escapes transaction directory: `{}`",
                    path.display()
                ),
            ));
        }
    }

    if journal.canonical == journal.staged
        || journal.canonical == journal.backup
        || journal.staged == journal.backup
        || journal_path == journal.canonical
        || journal_path == journal.staged
        || journal_path == journal.backup
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "update journal paths must be distinct",
        ));
    }

    Ok(())
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

#[allow(unsafe_code)]
fn open_process_for_wait(process_id: u32) -> io::Result<OwnedHandle> {
    let handle = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, false, process_id) }
        .map_err(|error| io::Error::other(error.to_string()))?;
    Ok(unsafe { OwnedHandle::from_raw_handle(handle.0) })
}

#[allow(unsafe_code)]
fn wait_for_process_exit(handle: &OwnedHandle, process_id: u32) -> io::Result<()> {
    let wait_result = unsafe { WaitForSingleObject(HANDLE(handle.as_raw_handle()), INFINITE) };
    if wait_result != WAIT_OBJECT_0 {
        return Err(io::Error::other(format!(
            "waiting for parent process {process_id} returned {wait_result:?}"
        )));
    }
    Ok(())
}
