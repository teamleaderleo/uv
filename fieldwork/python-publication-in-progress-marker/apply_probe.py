#!/usr/bin/env python3
"""Add fork-only failpoints and reversing integration tests for the marker candidate."""

from pathlib import Path
import sys

root = Path(sys.argv[1])

install = root / "crates/uv/src/commands/python/install.rs"
text = install.read_text(encoding="utf-8")
old = """                let installation = ManagedPythonInstallation::new(path, download);
                if let Some(ref sender) = bytecode_compilation_sender {
"""
new = """                let installation = ManagedPythonInstallation::new(path, download);
                if let Some(gate) =
                    std::env::var_os(\"UV_INTERNAL__TEST_PYTHON_INSTALL_PAUSE_AFTER_PUBLISH\")
                {
                    let gate = PathBuf::from(gate);
                    fs_err::write(gate.join(\"published\"), b\"published\")?;
                    while !gate.join(\"continue\").exists() {
                        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
                    }
                }
                if std::env::var_os(\"UV_INTERNAL__TEST_PYTHON_INSTALL_FAIL_AFTER_PUBLISH\").is_some()
                {
                    anyhow::bail!(\"injected managed Python failure after publication\");
                }
                if let Some(ref sender) = bytecode_compilation_sender {
"""
if text.count(old) != 1:
    raise SystemExit(
        f"managed publication probe insertion mismatch: expected 1, found {text.count(old)}"
    )
install.write_text(text.replace(old, new), encoding="utf-8")

tests = root / "crates/uv/tests/python/python_install.rs"
text = tests.read_text(encoding="utf-8")
marker = """#[test]
fn python_reinstall() {
"""
tests_to_add = r'''#[test]
#[cfg(unix)]
fn python_install_marker_hides_published_incomplete_installation() -> anyhow::Result<()> {
    let context = uv_test::test_context_with_versions!(&[])
        .with_filtered_python_keys()
        .with_filtered_exe_suffix()
        .with_filtered_latest_python_versions()
        .with_managed_python_dirs()
        .with_python_download_cache();

    let gate = context.temp_dir.child("publication-gate");
    gate.create_dir_all()?;
    let published = gate.child("published");
    let release = gate.child("continue");

    let mut install = context.python_install();
    install
        .arg("3.12.6")
        .env(
            "UV_INTERNAL__TEST_PYTHON_INSTALL_PAUSE_AFTER_PUBLISH",
            gate.path(),
        );
    let mut child = install.spawn().context("failed to spawn paused python install")?;

    let started = std::time::Instant::now();
    while !published.path().exists() {
        if started.elapsed() > std::time::Duration::from_secs(30) {
            let _ = child.kill();
            anyhow::bail!("managed Python publication pause was not reached");
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }

    let managed = context.temp_dir.child("managed");
    let installation = fs_err::read_dir(managed.path())?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .find(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("cpython-3.12.6-"))
        })
        .context("published managed Python installation was not visible")?;
    let in_progress = installation.join(".uv-installing");
    assert!(in_progress.is_file());

    let hidden = context.python_find().arg("3.12.6").output()?;
    assert!(
        !hidden.status.success(),
        "python find unexpectedly discovered marker-bearing installation: {}",
        String::from_utf8_lossy(&hidden.stdout)
    );

    release.touch()?;
    let install_status = child.wait()?;
    assert!(install_status.success());
    assert!(!in_progress.exists());
    context.python_find().arg("3.12.6").assert().success();

    Ok(())
}

#[test]
#[cfg(unix)]
fn python_install_marker_hides_failed_publication_residue() -> anyhow::Result<()> {
    let context = uv_test::test_context_with_versions!(&[])
        .with_filtered_python_keys()
        .with_filtered_exe_suffix()
        .with_filtered_latest_python_versions()
        .with_managed_python_dirs()
        .with_python_download_cache();

    let failed = context
        .python_install()
        .arg("3.12.6")
        .env("UV_INTERNAL__TEST_PYTHON_INSTALL_FAIL_AFTER_PUBLISH", "1")
        .output()?;
    assert!(!failed.status.success());

    let managed = context.temp_dir.child("managed");
    let installation = fs_err::read_dir(managed.path())?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .find(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("cpython-3.12.6-"))
        })
        .context("failed install did not leave a published directory")?;
    let in_progress = installation.join(".uv-installing");
    assert!(in_progress.is_file());

    context.python_find().arg("3.12.6").assert().failure();

    context.python_install().arg("3.12.6").assert().success();
    assert!(!in_progress.exists());
    context.python_find().arg("3.12.6").assert().success();

    Ok(())
}

#[test]
#[cfg(unix)]
fn python_reinstall_marker_hides_replaced_incomplete_installation() -> anyhow::Result<()> {
    let context = uv_test::test_context_with_versions!(&[])
        .with_filtered_python_keys()
        .with_filtered_exe_suffix()
        .with_filtered_latest_python_versions()
        .with_managed_python_dirs()
        .with_python_download_cache();

    context.python_install().arg("3.12.6").assert().success();
    context.python_find().arg("3.12.6").assert().success();

    let gate = context.temp_dir.child("reinstall-publication-gate");
    gate.create_dir_all()?;
    let published = gate.child("published");
    let release = gate.child("continue");

    let mut reinstall = context.python_install();
    reinstall
        .arg("--reinstall")
        .arg("3.12.6")
        .env(
            "UV_INTERNAL__TEST_PYTHON_INSTALL_PAUSE_AFTER_PUBLISH",
            gate.path(),
        );
    let mut child = reinstall.spawn().context("failed to spawn paused python reinstall")?;

    let started = std::time::Instant::now();
    while !published.path().exists() {
        if started.elapsed() > std::time::Duration::from_secs(30) {
            let _ = child.kill();
            anyhow::bail!("managed Python reinstall publication pause was not reached");
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }

    let managed = context.temp_dir.child("managed");
    let installation = fs_err::read_dir(managed.path())?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .find(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("cpython-3.12.6-"))
        })
        .context("reinstalled managed Python final directory was not visible")?;
    let in_progress = installation.join(".uv-installing");
    assert!(in_progress.is_file());

    // Existing version links from the prior successful installation still resolve into the
    // replaced final path. Managed discovery must not accept that path while the marker exists.
    let hidden = context.python_find().arg("3.12.6").output()?;
    assert!(
        !hidden.status.success(),
        "python find unexpectedly discovered paused reinstall: {}",
        String::from_utf8_lossy(&hidden.stdout)
    );

    release.touch()?;
    let reinstall_status = child.wait()?;
    assert!(reinstall_status.success());
    assert!(!in_progress.exists());
    context.python_find().arg("3.12.6").assert().success();

    Ok(())
}

'''
if text.count(marker) != 1:
    raise SystemExit(
        f"python install marker test insertion mismatch: expected 1, found {text.count(marker)}"
    )
tests.write_text(text.replace(marker, tests_to_add + marker), encoding="utf-8")

print(root)
