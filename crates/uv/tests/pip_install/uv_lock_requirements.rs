use anyhow::Result;
use assert_fs::prelude::*;
use uv_test::uv_snapshot;

#[test]
fn reject_project_uv_lock_as_requirements() -> Result<()> {
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
    assert!(context.temp_dir.child("uv.lock").path().is_file());

    uv_snapshot!(context.pip_install()
        .arg("-r")
        .arg("uv.lock")
        .arg("--strict"), @"
    exit_code: 2 (failure)
    ----- stderr -----
    error: The file `uv.lock` appears to be a uv lockfile, but requirements must be specified in `requirements.txt` format
    "
    );

    Ok(())
}

#[test]
fn reject_pep723_script_lock_as_requirements() -> Result<()> {
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
    assert!(context.temp_dir.child("action.py.lock").path().is_file());

    uv_snapshot!(context.pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict"), @"
    exit_code: 2 (failure)
    ----- stderr -----
    error: The file `action.py.lock` appears to be a uv lockfile, but requirements must be specified in `requirements.txt` format
    "
    );

    Ok(())
}

#[test]
fn accept_non_uv_lock_as_requirements() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context
        .temp_dir
        .child("action.py")
        .write_str("print('not a PEP 723 script')\n")?;
    context.temp_dir.child("action.py.lock").touch()?;

    uv_snapshot!(context.pip_install()
        .arg("-r")
        .arg("action.py.lock")
        .arg("--strict"), @"
    exit_code: 0 (success)
    ----- stderr -----
    warning: Requirements file `action.py.lock` does not contain any dependencies
    Checked in [TIME]
    "
    );

    Ok(())
}
