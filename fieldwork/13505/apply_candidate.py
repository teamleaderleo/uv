#!/usr/bin/env python3
"""Apply the uv #13505 Windows path-case regression and candidate."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_integration_test(root: Path) -> None:
    path = root / "crates/uv/tests/python/python_list.rs"
    marker = """    #[cfg(unix)]
    {
        // Construct a `PATH` with symlinks
"""
    block = """    #[cfg(windows)]
    {
        let original = std::env::split_paths(&context.python_path()).collect::<Vec<_>>();
        let case_variants = original
            .iter()
            .map(|path| {
                let mut value = path.as_os_str().to_os_string();
                value.make_ascii_lowercase();
                if value == path.as_os_str() {
                    value.make_ascii_uppercase();
                }
                std::path::PathBuf::from(value)
            })
            .collect::<Vec<_>>();

        assert!(
            original
                .iter()
                .zip(&case_variants)
                .any(|(left, right)| left != right)
        );

        let path = std::env::join_paths(original.iter().chain(&case_variants)).unwrap();

        uv_snapshot!(context.filters(), context.python_list().env(EnvVars::UV_PYTHON_SEARCH_PATH, &path), @\"
        exit_code: 0 (success)
        ----- stdout -----
        cpython-3.12.[X]-[PLATFORM] [PYTHON-3.12]
        cpython-3.11.[X]-[PLATFORM] [PYTHON-3.11]
        \"\);
    }

"""
    replace_once(path, marker, block + marker, "Windows integration control")


def apply_candidate(root: Path) -> None:
    windows_lib = root / "crates/uv-windows/src/lib.rs"
    replace_once(
        windows_lib,
        """mod job;
#[cfg(feature = \"std\")]
mod spawn;
""",
        """mod job;
#[cfg(feature = \"std\")]
mod path;
#[cfg(feature = \"std\")]
mod spawn;
""",
        "uv-windows module declaration",
    )
    replace_once(
        windows_lib,
        """pub use job::{Job, JobError};
#[cfg(feature = \"std\")]
pub use spawn::spawn_child;
""",
        """pub use job::{Job, JobError};
#[cfg(feature = \"std\")]
pub use path::path_eq_ignore_case;
#[cfg(feature = \"std\")]
pub use spawn::spawn_child;
""",
        "uv-windows export",
    )

    windows_path = root / "crates/uv-windows/src/path.rs"
    if windows_path.exists():
        raise SystemExit(f"candidate path already exists: {windows_path}")
    windows_path.write_text(
        """use std::os::windows::ffi::OsStrExt;
use std::path::Path;

use windows::Win32::Globalization::{CSTR_EQUAL, CompareStringOrdinal};

/// Compare two Windows paths using ordinal case-insensitive string semantics.
///
/// This is a lexical comparison. It does not access the filesystem, resolve
/// symlinks, or collapse distinct queried paths that happen to identify the
/// same file.
pub fn path_eq_ignore_case(left: &Path, right: &Path) -> bool {
    let left = left.as_os_str().encode_wide().collect::<Vec<_>>();
    let right = right.as_os_str().encode_wide().collect::<Vec<_>>();

    // SAFETY: Both slices remain alive for the duration of the call. The
    // windows 0.61 binding supplies their lengths to CompareStringOrdinal.
    unsafe { CompareStringOrdinal(&left, &right, true) == CSTR_EQUAL }
}
""",
        encoding="utf-8",
    )

    list_rs = root / "crates/uv/src/commands/python/list.rs"
    replace_once(
        list_rs,
        """use std::collections::BTreeSet;
use std::fmt::Write;
use uv_cli::PythonListFormat;
""",
        """use std::collections::BTreeSet;
use std::fmt::Write;
use std::path::Path;
use uv_cli::PythonListFormat;
""",
        "list path import",
    )
    replace_once(
        list_rs,
        """enum Kind {
    Download,
    Managed,
    System,
}

#[derive(Debug, Serialize)]
""",
        """enum Kind {
    Download,
    Managed,
    System,
}

#[cfg(windows)]
fn insert_seen_path<'path>(seen_paths: &mut Vec<&'path Path>, path: &'path Path) -> bool {
    if seen_paths
        .iter()
        .any(|seen| uv_windows::path_eq_ignore_case(seen, path))
    {
        false
    } else {
        seen_paths.push(path);
        true
    }
}

#[cfg(not(windows))]
fn insert_seen_path<'path>(
    seen_paths: &mut FxHashSet<&'path Path>,
    path: &'path Path,
) -> bool {
    seen_paths.insert(path)
}

#[cfg(all(test, windows))]
mod tests {
    use super::insert_seen_path;
    use std::path::Path;

    #[test]
    fn windows_path_case_variants_are_deduplicated() {
        let mut seen_paths = Vec::new();

        assert!(insert_seen_path(
            &mut seen_paths,
            Path::new(r\"C:\\München\\Python\\python.exe\")
        ));
        assert!(!insert_seen_path(
            &mut seen_paths,
            Path::new(r\"c:\\MÜNCHEN\\python\\PYTHON.EXE\")
        ));
        assert!(insert_seen_path(
            &mut seen_paths,
            Path::new(r\"C:\\Shims\\python.exe\")
        ));
    }
}

#[derive(Debug, Serialize)]
""",
        "list seen-path helper",
    )
    replace_once(
        list_rs,
        """    let mut seen_minor = FxHashSet::default();
    let mut seen_patch = FxHashSet::default();
    let mut seen_paths = FxHashSet::default();
    let mut include = Vec::new();
""",
        """    let mut seen_minor = FxHashSet::default();
    let mut seen_patch = FxHashSet::default();
    #[cfg(windows)]
    let mut seen_paths = Vec::new();
    #[cfg(not(windows))]
    let mut seen_paths = FxHashSet::default();
    let mut include = Vec::new();
""",
        "seen-path storage",
    )
    replace_once(
        list_rs,
        """        if let Either::Left(path) = uri {
            if !seen_paths.insert(path) {
                continue;
            }
        }
""",
        """        if let Either::Left(path) = uri {
            if !insert_seen_path(&mut seen_paths, path) {
                continue;
            }
        }
""",
        "seen-path insertion",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    apply_integration_test(root)
    if not args.tests_only:
        apply_candidate(root)


if __name__ == "__main__":
    main()
