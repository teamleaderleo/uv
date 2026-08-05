#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement anchor, found {count}")
    path.write_text(content.replace(old, new, 1))


cargo_toml = Path("crates/uv-requirements/Cargo.toml")
replace_once(
    cargo_toml,
    "uv-distribution-types = { workspace = true }\n",
    "uv-distribution-types = { workspace = true }\nuv-errors = { workspace = true }\n",
)

specification = Path("crates/uv-requirements/src/specification.rs")
replace_once(
    specification,
    "use std::collections::BTreeMap;\nuse std::path::{Path, PathBuf};\n",
    "use std::collections::BTreeMap;\nuse std::ffi::OsStr;\nuse std::fmt;\nuse std::path::{Path, PathBuf};\n",
)
replace_once(
    specification,
    "use uv_distribution_types::{\n    IndexUrl, NameRequirementSpecification, UnresolvedRequirement,\n    UnresolvedRequirementSpecification,\n};\nuse uv_fs::{CWD, Simplified};\n",
    "use uv_distribution_types::{\n    IndexUrl, NameRequirementSpecification, UnresolvedRequirement,\n    UnresolvedRequirementSpecification,\n};\nuse uv_errors::{Hint, Hints};\nuse uv_fs::{CWD, Simplified};\n",
)
replace_once(
    specification,
    "use uv_requirements_txt::{RequirementsTxt, RequirementsTxtRequirement, SourceCache};\n",
    "use uv_requirements_txt::{\n    RequirementsTxt, RequirementsTxtFileError, RequirementsTxtRequirement, SourceCache,\n};\nuse uv_resolver::{Lock, LockParseError};\n",
)
replace_once(
    specification,
    "use crate::{RequirementsSource, SourceTree};\n\n#[derive(Debug, Default, Clone)]\n",
    '''use crate::{RequirementsSource, SourceTree};

#[derive(Debug, Clone)]
enum UvLockfileKind {
    Project,
    Script(PathBuf),
    Other,
}

/// A uv lockfile was passed through a requirements-file input.
#[derive(Debug)]
pub struct UvLockfileAsRequirementsError {
    path: PathBuf,
    kind: UvLockfileKind,
    source: RequirementsTxtFileError,
}

impl fmt::Display for UvLockfileAsRequirementsError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "The file `{}` appears to be a uv lockfile, but requirements must be specified in `requirements.txt` format",
            self.path.user_display(),
        )
    }
}

impl std::error::Error for UvLockfileAsRequirementsError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.source)
    }
}

impl Hint for UvLockfileAsRequirementsError {
    fn hints(&self) -> Hints<'_> {
        match &self.kind {
            UvLockfileKind::Project => Hints::from(
                "Use `uv sync` or `uv export --format requirements-txt` from the owning project, or provide requirements directly instead",
            ),
            UvLockfileKind::Script(script) => Hints::from(format!(
                "Use `uv run {0}` to run the script, or `uv export --script {0} --format requirements-txt` to create a requirements file",
                script.user_display(),
            )),
            UvLockfileKind::Other => Hints::from(
                "Use the uv command that created this lockfile, or provide requirements directly instead",
            ),
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum SourceRole {
    Requirement,
    Other,
}

fn uv_lockfile_kind(path: &Path, contents: Option<&str>) -> Option<UvLockfileKind> {
    let contents = contents?;
    if !matches!(
        Lock::from_toml(contents),
        Ok(_)
            | Err(
                LockParseError::UnsupportedVersion { .. }
                    | LockParseError::UnparsableVersion { .. }
            )
    ) {
        return None;
    }

    if path.file_name() == Some(OsStr::new("uv.lock")) {
        return Some(UvLockfileKind::Project);
    }

    if path.extension() == Some(OsStr::new("lock")) {
        let script_path = path.with_file_name(path.file_stem()?);
        if let Ok(contents) = fs_err::read(&script_path)
            && Pep723Metadata::parse(&contents)
                .is_ok_and(|metadata| metadata.is_some())
        {
            return Some(UvLockfileKind::Script(script_path));
        }
    }

    Some(UvLockfileKind::Other)
}

#[derive(Debug, Default, Clone)]
''',
)
replace_once(
    specification,
    "        Self::from_source_with_cache(source, client_builder, &mut SourceCache::default()).await\n",
    "        Self::from_source_with_cache(\n            source,\n            client_builder,\n            SourceRole::Requirement,\n            &mut SourceCache::default(),\n        )\n        .await\n",
)
replace_once(
    specification,
    "    async fn from_source_with_cache(\n        source: &RequirementsSource,\n        client_builder: &BaseClientBuilder<'_>,\n        cache: &mut SourceCache,\n    ) -> Result<Self> {\n",
    "    async fn from_source_with_cache(\n        source: &RequirementsSource,\n        client_builder: &BaseClientBuilder<'_>,\n        role: SourceRole,\n        cache: &mut SourceCache,\n    ) -> Result<Self> {\n",
)
replace_once(
    specification,
    '''                let requirements_txt =
                    RequirementsTxt::parse_with_cache(path, &*CWD, client_builder, cache).await?;
''',
    '''                let requirements_txt = match RequirementsTxt::parse_with_cache(
                    path,
                    &*CWD,
                    client_builder,
                    cache,
                )
                .await
                {
                    Ok(requirements_txt) => requirements_txt,
                    Err(source) => {
                        if matches!(role, SourceRole::Requirement)
                            && let Some(kind) = uv_lockfile_kind(
                                path,
                                cache.get(path.as_path()).map(String::as_str),
                            )
                        {
                            return Err(anyhow::Error::new(UvLockfileAsRequirementsError {
                                path: path.clone(),
                                kind,
                                source,
                            }));
                        }
                        return Err(source.into());
                    }
                };
''',
)
replace_once(
    specification,
    '''        for source in requirements {
            let source = Self::from_source_with_cache(source, client_builder, &mut cache).await?;
            requirement_sources.push(source);
        }
''',
    '''        for source in requirements {
            let source = Self::from_source_with_cache(
                source,
                client_builder,
                SourceRole::Requirement,
                &mut cache,
            )
            .await?;
            requirement_sources.push(source);
        }
''',
)
replace_once(
    specification,
    '''        for source in constraints {
            let source = Self::from_source_with_cache(source, client_builder, &mut cache).await?;
''',
    '''        for source in constraints {
            let source = Self::from_source_with_cache(
                source,
                client_builder,
                SourceRole::Other,
                &mut cache,
            )
            .await?;
''',
)
replace_once(
    specification,
    '''        for source in overrides {
            let source = Self::from_source_with_cache(source, client_builder, &mut cache).await?;
''',
    '''        for source in overrides {
            let source = Self::from_source_with_cache(
                source,
                client_builder,
                SourceRole::Other,
                &mut cache,
            )
            .await?;
''',
)
replace_once(
    specification,
    '''        for source in excludes {
            let source = Self::from_source_with_cache(source, client_builder, &mut cache).await?;
''',
    '''        for source in excludes {
            let source = Self::from_source_with_cache(
                source,
                client_builder,
                SourceRole::Other,
                &mut cache,
            )
            .await?;
''',
)

diagnostics = Path("crates/uv/src/commands/diagnostics.rs")
replace_once(
    diagnostics,
    "        collect_hint::<ExtrasWithoutSourceError>(cause, &mut hints);\n",
    "        collect_hint::<ExtrasWithoutSourceError>(cause, &mut hints);\n        collect_hint::<uv_requirements::UvLockfileAsRequirementsError>(cause, &mut hints);\n",
)

main = Path("crates/uv/tests/pip_install/main.rs")
replace_once(
    main,
    '''#[cfg(all(feature = "test-python", feature = "test-pypi"))]
mod pip_install;
''',
    '''#[cfg(all(feature = "test-python", feature = "test-pypi"))]
mod pip_install;

#[cfg(all(feature = "test-python", feature = "test-pypi"))]
mod uv_lock_requirements_hint;
''',
)

Path("crates/uv/tests/pip_install/uv_lock_requirements_hint.rs").write_text(
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
fn project_uv_lock_has_dedicated_error_and_hint() -> Result<()> {
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
            predicate::str::contains("The file `uv.lock` appears to be a uv lockfile")
                .and(predicate::str::contains(
                    "Caused by: Couldn't parse requirement in `uv.lock` at position 0",
                ))
                .and(predicate::str::contains(
                    "\nhint: Use `uv sync` or `uv export --format requirements-txt` from the owning project",
                )),
        );

    Ok(())
}

#[test]
fn script_uv_lock_has_dedicated_error_and_hint() -> Result<()> {
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
            predicate::str::contains("The file `action.py.lock` appears to be a uv lockfile")
                .and(predicate::str::contains(
                    "Caused by: Couldn't parse requirement in `action.py.lock` at position 0",
                ))
                .and(predicate::str::contains("\nhint: Use `uv run action.py`"))
                .and(predicate::str::contains(
                    "`uv export --script action.py --format requirements-txt`",
                )),
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
        .stderr(
            predicate::str::contains("does not contain any dependencies")
                .and(predicate::str::contains("appears to be a uv lockfile").not()),
        );

    Ok(())
}

#[test]
fn script_shaped_non_lock_keeps_original_parse_error() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context.temp_dir.child("action.py").write_str(
        "# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n",
    )?;
    context
        .temp_dir
        .child("action.py.lock")
        .write_str("version = 1\n")?;

    context
        .pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains(
                "Couldn't parse requirement in `action.py.lock` at position 0",
            )
            .and(predicate::str::contains("appears to be a uv lockfile").not())
            .and(predicate::str::contains("\nhint:").not()),
        );

    Ok(())
}

#[test]
fn orphaned_script_lock_has_generic_hint() -> Result<()> {
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
    std::fs::remove_file(context.temp_dir.child("action.py").path())?;

    context
        .pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("The file `action.py.lock` appears to be a uv lockfile")
                .and(predicate::str::contains(
                    "\nhint: Use the uv command that created this lockfile",
                )),
        );

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
            predicate::str::contains("Couldn't parse requirement in `poetry.lock` at position 0")
                .and(predicate::str::contains("appears to be a uv lockfile").not())
                .and(predicate::str::contains("\nhint:").not()),
        );

    Ok(())
}

#[test]
fn uv_lock_constraint_keeps_original_parse_error() -> Result<()> {
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
        .arg("anyio")
        .arg("-c")
        .arg("uv.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("Couldn't parse requirement in `uv.lock` at position 0")
                .and(predicate::str::contains("appears to be a uv lockfile").not())
                .and(predicate::str::contains("\nhint:").not()),
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
        .stderr(
            predicate::str::contains("appears to be a uv lockfile")
                .and(predicate::str::contains("\nhint: Use `uv run")),
        );

    Ok(())
}
'''
)
