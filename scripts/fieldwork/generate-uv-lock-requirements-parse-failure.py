#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement anchor, found {count}")
    path.write_text(content.replace(old, new, 1))


sources = Path("crates/uv-requirements/src/sources.rs")
replace_once(
    sources,
    "use uv_requirements_txt::RequirementsTxtRequirement;\n",
    "use uv_requirements_txt::RequirementsTxtRequirement;\nuse uv_scripts::Pep723Metadata;\n",
)
replace_once(
    sources,
    "/// Returns `true` if a file name matches the `pylock.toml` pattern defined in PEP 751.\n",
    '''/// Returns `true` if a path identifies a lockfile that uv itself generates.\n///\n/// This check is only used after requirements parsing has failed. A valid requirements file wins\n/// regardless of its filename.\npub(crate) fn is_uv_lockfile(path: &Path) -> bool {\n    if !path.is_file() {\n        return false;\n    }\n\n    let Some(file_name) = path.file_name() else {\n        return false;\n    };\n\n    if file_name == OsStr::new("uv.lock") {\n        return true;\n    }\n\n    if path.extension() != Some(OsStr::new("lock")) {\n        return false;\n    }\n    let Some(script_name) = path.file_stem() else {\n        return false;\n    };\n    let script_path = path.with_file_name(script_name);\n    let Ok(contents) = fs_err::read(script_path) else {\n        return false;\n    };\n\n    Pep723Metadata::parse(&contents).is_ok_and(|metadata| metadata.is_some())\n}\n\n/// Returns `true` if a file name matches the `pylock.toml` pattern defined in PEP 751.\n''',
)

specification = Path("crates/uv-requirements/src/specification.rs")
replace_once(
    specification,
    "use crate::{RequirementsSource, SourceTree};\n",
    "use crate::{RequirementsSource, SourceTree, is_uv_lockfile};\n",
)
replace_once(
    specification,
    '''        for source in requirements {\n            let source = Self::from_source_with_cache(source, client_builder, &mut cache).await?;\n            requirement_sources.push(source);\n        }\n''',
    '''        for source in requirements {\n            let parsed = Self::from_source_with_cache(source, client_builder, &mut cache).await;\n            let source = match parsed {\n                Ok(source) => source,\n                Err(err) => {\n                    if let RequirementsSource::RequirementsTxt(path) = source\n                        && is_uv_lockfile(path)\n                    {\n                        return Err(err.context(format!(\n                            "The file `{}` appears to be a uv lockfile, but requirements must be specified in `requirements.txt` format. Use `uv sync` or `uv export` instead",\n                            path.user_display(),\n                        )));\n                    }\n                    return Err(err);\n                }\n            };\n            requirement_sources.push(source);\n        }\n''',
)

main = Path("crates/uv/tests/pip_install/main.rs")
replace_once(
    main,
    '''#[cfg(all(feature = "test-python", feature = "test-pypi"))]\nmod pip_install;\n''',
    '''#[cfg(all(feature = "test-python", feature = "test-pypi"))]\nmod pip_install;\n\n#[cfg(all(feature = "test-python", feature = "test-pypi"))]\nmod uv_lock_requirements_parse_failure;\n''',
)

Path("crates/uv/tests/pip_install/uv_lock_requirements_parse_failure.rs").write_text(
    r'''#[cfg(unix)]
use std::ffi::OsString;
#[cfg(unix)]
use std::os::unix::ffi::OsStringExt;
#[cfg(unix)]
use std::path::Path;

use anyhow::Result;
use assert_fs::prelude::*;
use predicates::prelude::*;

#[test]
fn project_uv_lock_adds_context_after_parse_failure() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context.temp_dir.child("pyproject.toml").write_str(
        r#"
        [project]
        name = "project"
        version = "0.1.0"
        requires-python = ">=3.12"
        dependencies = []
        "#,
    )?;

    context.lock().assert().success();

    context
        .pip_install()
        .arg("-r")
        .arg("uv.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("appears to be a uv lockfile")
                .and(predicate::str::contains("Use `uv sync` or `uv export` instead"))
                .and(predicate::str::contains("Couldn't parse requirement")),
        );

    Ok(())
}

#[test]
fn script_uv_lock_adds_context_after_parse_failure() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context.temp_dir.child("action.py").write_str(
        "# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n",
    )?;

    context
        .lock()
        .arg("--script")
        .arg("action.py")
        .assert()
        .success();

    context
        .pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("appears to be a uv lockfile")
                .and(predicate::str::contains("Couldn't parse requirement")),
        );

    Ok(())
}

#[test]
fn valid_requirements_file_wins_over_script_lock_name() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context.temp_dir.child("action.py").write_str(
        "# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n",
    )?;
    context
        .temp_dir
        .child("action.py.lock")
        .write_str("# Valid, empty requirements file.\n")?;

    context
        .pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict")
        .assert()
        .success()
        .stderr(predicate::str::contains("does not contain any dependencies"));

    Ok(())
}

#[test]
fn unrelated_lock_keeps_original_parse_error() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context
        .temp_dir
        .child("poetry.lock")
        .write_str("version = 1\n")?;

    context
        .pip_install()
        .arg("-r")
        .arg("poetry.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("Couldn't parse requirement")
                .and(predicate::str::contains("appears to be a uv lockfile").not()),
        );

    Ok(())
}

#[cfg(unix)]
#[test]
fn non_utf8_script_uv_lock_is_recognized() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let script_name = OsString::from_vec(b"action-\xff.py".to_vec());
    context
        .temp_dir
        .child(Path::new(&script_name))
        .write_str("# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n")?;

    context
        .lock()
        .arg("--script")
        .arg(&script_name)
        .assert()
        .success();

    let mut lock_name = script_name;
    lock_name.push(".lock");
    context
        .pip_install()
        .arg("-r")
        .arg(&lock_name)
        .arg("--strict")
        .assert()
        .failure()
        .stderr(predicate::str::contains("appears to be a uv lockfile"));

    Ok(())
}
'''
)
