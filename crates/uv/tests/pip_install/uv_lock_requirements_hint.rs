use anyhow::Result;
use assert_cmd::assert::OutputAssertExt;
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
    context
        .temp_dir
        .child("action.py")
        .write_str("# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n")?;
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
                .and(predicate::str::contains("\nhint: Use `uv run <script>`"))
                .and(predicate::str::contains(
                    "`uv export --script <script> --format requirements-txt`",
                )),
        );

    Ok(())
}

#[test]
fn valid_requirements_file_wins_over_script_lock_name() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context
        .temp_dir
        .child("action.py")
        .write_str("# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n")?;
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
    context
        .temp_dir
        .child("action.py")
        .write_str("# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n")?;
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
fn incomplete_future_version_toml_keeps_original_parse_error() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context
        .temp_dir
        .child("future.lock")
        .write_str("version = 2\nrevision = 1\n")?;

    context
        .pip_install()
        .arg("-r")
        .arg("future.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("Couldn't parse requirement in `future.lock` at position 0")
                .and(predicate::str::contains("appears to be a uv lockfile").not())
                .and(predicate::str::contains("\nhint:").not()),
        );

    Ok(())
}

#[test]
fn orphaned_script_lock_has_generic_hint() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context
        .temp_dir
        .child("action.py")
        .write_str("# /// script\n# dependencies = []\n# ///\n\nprint('hello')\n")?;
    context
        .lock()
        .arg("--script")
        .arg("action.py")
        .assert()
        .success();
    fs_err::remove_file(context.temp_dir.child("action.py").path())?;

    context
        .pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict")
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("The file `action.py.lock` appears to be a uv lockfile").and(
                predicate::str::contains("\nhint: Use the uv command that created this lockfile"),
            ),
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
