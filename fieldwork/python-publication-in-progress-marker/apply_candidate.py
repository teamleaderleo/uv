#!/usr/bin/env python3
"""Apply a bounded managed-Python in-progress publication marker candidate."""

from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(path: Path, old: str, new: str, *, name: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{name} mismatch in {path}: expected {count}, found {actual}")
    path.write_text(text.replace(old, new), encoding="utf-8")


managed = root / "crates/uv-python/src/managed.rs"
replace(
    managed,
    """use crate::{PythonInstallationMinorVersionKey, PythonVariant, macos_dylib, sysconfig};

#[derive(Error, Debug)]
""",
    """use crate::{PythonInstallationMinorVersionKey, PythonVariant, macos_dylib, sysconfig};

pub(crate) const MANAGED_PYTHON_IN_PROGRESS_MARKER: &str = ".uv-installing";

fn installation_is_in_progress(path: &Path) -> Result<bool, Error> {
    match fs::symlink_metadata(path.join(MANAGED_PYTHON_IN_PROGRESS_MARKER)) {
        Ok(_) => Ok(true),
        Err(err) if err.kind() == io::ErrorKind::NotFound => Ok(false),
        Err(err) => Err(Error::ReadError(err)),
    }
}

#[derive(Error, Debug)]
""",
    name="marker constant and helper",
)
replace(
    managed,
    """        let scratch = self.scratch();
        Ok(dirs
            .into_iter()
            // Ignore the scratch directory
            .filter(|path| *path != scratch)
            // Ignore any `.` prefixed directories
            .filter(|path| {
                path.file_name()
                    .and_then(OsStr::to_str)
                    .is_none_or(|name| !name.starts_with('.'))
            })
            .filter_map(|path| {
""",
    """        let scratch = self.scratch();
        let dirs = dirs
            .into_iter()
            // Ignore the scratch directory
            .filter(|path| *path != scratch)
            // Ignore any `.` prefixed directories
            .filter(|path| {
                path.file_name()
                    .and_then(OsStr::to_str)
                    .is_none_or(|name| !name.starts_with('.'))
            })
            // Published managed Pythons remain hidden until internal finalization succeeds.
            // Any marker object means incomplete; unexpected marker metadata errors abort
            // directory discovery rather than exposing a possibly incomplete installation.
            .map(|path| {
                if installation_is_in_progress(&path)? {
                    debug!(
                        "Skipping incomplete managed Python installation at `{}`",
                        path.user_display()
                    );
                    Ok(None)
                } else {
                    Ok(Some(path))
                }
            })
            .collect::<Result<Vec<_>, Error>>()?;

        Ok(dirs.into_iter().flatten().filter_map(|path| {
""",
    name="fail-closed discovery marker gate",
)
replace(
    managed,
    """        // Construct the installation from the path within the managed root
        let path = root.join(name);
        Self::from_path(path).ok()
""",
    """        // Construct the installation from the path within the managed root. Refuse
        // marker-bearing (or unreadable) paths here too: this reconstruction path can be reached
        // from an already-discovered interpreter without going through `find_all()`.
        let path = root.join(name);
        if installation_is_in_progress(&path).ok()? {
            return None;
        }
        Self::from_path(path).ok()
""",
    name="interpreter reconstruction marker gate",
)
replace(
    managed,
    """    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn key(&self) -> &PythonInstallationKey {
""",
    """    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Mark this published installation complete after all internal finalization succeeds.
    pub fn mark_finalized(&self) -> Result<(), Error> {
        let marker = self.path.join(MANAGED_PYTHON_IN_PROGRESS_MARKER);
        match fs::remove_file(marker) {
            Ok(()) => Ok(()),
            Err(err) if err.kind() == io::ErrorKind::NotFound => Ok(()),
            Err(err) => Err(err.into()),
        }
    }

    pub fn key(&self) -> &PythonInstallationKey {
""",
    name="finalization marker removal",
)
replace(
    managed,
    """    #[test]
    fn test_is_upgrade_of_same_version() {
""",
    """    #[test]
    #[cfg(unix)]
    fn find_all_skips_in_progress_installations() {
        let installations = ManagedPythonInstallations::temp().unwrap().init().unwrap();
        let platform = Platform::from_str("linux-x86_64-gnu").unwrap();
        let key = PythonInstallationKey::new(
            LenientImplementationName::Known(ImplementationName::CPython),
            3,
            12,
            6,
            None,
            platform,
            PythonVariant::Default,
        );
        let path = installations.root().join(key.to_string());
        fs::create_dir_all(&path).unwrap();
        let marker = path.join(MANAGED_PYTHON_IN_PROGRESS_MARKER);

        fs::write(&marker, b"in-progress").unwrap();
        assert!(installation_is_in_progress(&path).unwrap());
        assert_eq!(installations.find_all().unwrap().count(), 0);
        fs::remove_file(&marker).unwrap();

        // Presence, not file type, owns the incomplete state.
        fs::create_dir(&marker).unwrap();
        assert!(installation_is_in_progress(&path).unwrap());
        assert_eq!(installations.find_all().unwrap().count(), 0);
        fs::remove_dir(&marker).unwrap();

        assert!(!installation_is_in_progress(&path).unwrap());
        let found = installations.find_all().unwrap().collect::<Vec<_>>();
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].key(), &key);
    }

    #[test]
    fn test_is_upgrade_of_same_version() {
""",
    name="marker discovery unit test",
)

downloads = root / "crates/uv-python/src/downloads.rs"
replace(
    downloads,
    "use crate::managed::ManagedPythonInstallation;\n",
    "use crate::managed::{MANAGED_PYTHON_IN_PROGRESS_MARKER, ManagedPythonInstallation};\n",
    name="downloads marker import",
)
replace(
    downloads,
    """        // Remove the target if it already exists.
        if path.is_dir() {
""",
    """        // Publish an explicit internal-finalization state with the installation. The marker
        // is created before the final rename so every newly visible generation starts incomplete.
        fs_err::write(extracted.join(MANAGED_PYTHON_IN_PROGRESS_MARKER), b"in-progress")?;

        // Remove the target if it already exists.
        if path.is_dir() {
""",
    name="pre-publication marker creation",
)

command_install = root / "crates/uv/src/commands/python/install.rs"
replace(
    command_install,
    """        if let Err(e) = installation.ensure_dylib_patched() {
            e.warn_user(installation);
        }

        let upgradeable = (default || is_default_install)
""",
    """        if let Err(e) = installation.ensure_dylib_patched() {
            e.warn_user(installation);
        }
        installation.mark_finalized()?;

        let upgradeable = (default || is_default_install)
""",
    name="command finalization marker removal",
)

installation = root / "crates/uv-python/src/installation.rs"
replace(
    installation,
    """        if let Err(e) = installed.ensure_dylib_patched() {
            e.warn_user(&installed);
        }

        Ok(Self {
""",
    """        if let Err(e) = installed.ensure_dylib_patched() {
            e.warn_user(&installed);
        }
        installed.mark_finalized()?;

        Ok(Self {
""",
    name="library fetch marker removal",
)

print(root)
