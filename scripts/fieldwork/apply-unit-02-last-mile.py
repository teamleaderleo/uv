#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WHEEL = Path("crates/uv-install-wheel/src/wheel.rs")
VIRTUALENV = Path("crates/uv-virtualenv/src/virtualenv.rs")
RUN = Path("crates/uv/src/commands/project/run.rs")
VENV_TEST = Path("crates/uv/tests/python/venv.rs")

SOURCE_EXPECTED = {
    WHEEL: {"realpath --": 2, "dirname --": 2},
    VIRTUALENV: {"realpath --": 2, "dirname --": 4},
    RUN: {"realpath --": 1, "dirname --": 1},
}
TEST_EXPECTED = {
    VENV_TEST: {"realpath --": 2, "dirname --": 4},
}


def replace_delimiters(paths: dict[Path, dict[str, int]]) -> dict[str, int]:
    totals = {"realpath --": 0, "dirname --": 0}
    for path, expected in paths.items():
        text = path.read_text()
        counts = {needle: text.count(needle) for needle in totals}
        if counts != expected:
            raise SystemExit(f"unexpected delimiter counts in {path}: {counts} != {expected}")
        path.write_text(text.replace("realpath --", "realpath").replace("dirname --", "dirname"))
        for needle, count in counts.items():
            totals[needle] += count
    return totals


source_totals = replace_delimiters(SOURCE_EXPECTED)
test_totals = replace_delimiters(TEST_EXPECTED)
if source_totals != {"realpath --": 5, "dirname --": 7}:
    raise SystemExit(f"unexpected source replacement totals: {source_totals}")
if test_totals != {"realpath --": 2, "dirname --": 4}:
    raise SystemExit(f"unexpected test replacement totals: {test_totals}")

run_text = RUN.read_text()
function_marker = """/// Create a copy of the entrypoint at `source` at `target`, if it has a Python shebang, replacing
/// the previous Python executable with a new one.
///
/// This is a no-op if the target already exists.
///
/// Note on Windows, the entrypoints do not use shebangs and require a rewrite of the trampoline.
#[cfg(unix)]
fn copy_entrypoint(
"""
constants = r"""#[cfg(unix)]
const RELOCATABLE_SHEBANG: &str = r#"#!/bin/sh
'''exec' "$(dirname "$(realpath "$0")")"/'python' "$0" "$@"
' '''
"#;

#[cfg(unix)]
const RELOCATABLE_PYTHON3_SHEBANG: &str = r#"#!/bin/sh
'''exec' "$(dirname "$(realpath "$0")")"/'python3' "$0" "$@"
' '''
"#;

#[cfg(unix)]
const LEGACY_RELOCATABLE_SHEBANG: &str = r#"#!/bin/sh
'''exec' "$(dirname -- "$(realpath -- "$0")")"/'python' "$0" "$@"
' '''
"#;

#[cfg(unix)]
const LEGACY_RELOCATABLE_PYTHON3_SHEBANG: &str = r#"#!/bin/sh
'''exec' "$(dirname -- "$(realpath -- "$0")")"/'python3' "$0" "$@"
' '''
"#;

"""
if run_text.count(function_marker) != 1:
    raise SystemExit("copy_entrypoint function marker changed")
run_text = run_text.replace(function_marker, constants + function_marker, 1)

old_recognizer = r"""    let Some(contents) = contents
        // Check for a relative path or relocatable shebang
        .strip_prefix(
            r#"#!/bin/sh
'''exec' "$(dirname "$(realpath "$0")")"/'python' "$0" "$@"
' '''
"#,
        )
        // Or, an absolute path shebang
"""
new_recognizer = """    let Some(contents) = contents
        // Check for corrected relocatable shebangs.
        .strip_prefix(RELOCATABLE_SHEBANG)
        .or_else(|| contents.strip_prefix(RELOCATABLE_PYTHON3_SHEBANG))
        // Keep recognizing launchers generated before BusyBox compatibility was fixed.
        .or_else(|| contents.strip_prefix(LEGACY_RELOCATABLE_SHEBANG))
        .or_else(|| contents.strip_prefix(LEGACY_RELOCATABLE_PYTHON3_SHEBANG))
        // Or, an absolute path shebang
"""
if run_text.count(old_recognizer) != 1:
    raise SystemExit("relocatable shebang recognizer changed")
run_text = run_text.replace(old_recognizer, new_recognizer, 1)

if "copy_entrypoint_accepts_current_and_legacy_relocatable_shebangs" in run_text:
    raise SystemExit("copy_entrypoint compatibility test already exists")

tests = r'''

#[cfg(all(test, unix))]
mod tests {
    use std::os::unix::fs::PermissionsExt;
    use std::path::Path;

    use super::{
        LEGACY_RELOCATABLE_PYTHON3_SHEBANG, LEGACY_RELOCATABLE_SHEBANG,
        RELOCATABLE_PYTHON3_SHEBANG, RELOCATABLE_SHEBANG, copy_entrypoint,
    };

    fn assert_relocatable_shebang_is_copied(shebang: &str) {
        let temp_dir = tempfile::tempdir().unwrap();
        let source = temp_dir.path().join("source-entrypoint");
        let target = temp_dir.path().join("target-entrypoint");
        fs_err::write(&source, format!("{shebang}print('probe')\n")).unwrap();

        let mut permissions = fs_err::metadata(&source).unwrap().permissions();
        permissions.set_mode(0o751);
        fs_err::set_permissions(&source, permissions).unwrap();

        copy_entrypoint(
            &source,
            &target,
            Path::new("/old/environment/bin/python3"),
            Path::new("/new/environment/bin/python"),
        )
        .unwrap();

        assert_eq!(
            fs_err::read_to_string(&target).unwrap(),
            "#!/new/environment/bin/python\nprint('probe')\n"
        );
        assert_eq!(
            fs_err::metadata(&target).unwrap().permissions().mode() & 0o777,
            0o751
        );
    }

    #[test]
    fn copy_entrypoint_accepts_current_and_legacy_relocatable_shebangs() {
        for shebang in [
            RELOCATABLE_SHEBANG,
            RELOCATABLE_PYTHON3_SHEBANG,
            LEGACY_RELOCATABLE_SHEBANG,
            LEGACY_RELOCATABLE_PYTHON3_SHEBANG,
        ] {
            assert_relocatable_shebang_is_copied(shebang);
        }
    }
}
'''
run_text += tests
RUN.write_text(run_text)

if RUN.read_text().count("realpath --") != 2 or RUN.read_text().count("dirname --") != 2:
    raise SystemExit("legacy delimiter forms must remain exactly twice in run.rs")
if VENV_TEST.read_text().count("realpath --") or VENV_TEST.read_text().count("dirname --"):
    raise SystemExit("relocatable venv expectations still contain unsupported delimiters")

print("UNIT_02_SOURCE_REPLACED=realpath:5,dirname:7")
print("UNIT_02_TEST_EXPECTATIONS=realpath:2,dirname:4")
print("UNIT_02_LEGACY_RECOGNIZER=realpath:2,dirname:2")
