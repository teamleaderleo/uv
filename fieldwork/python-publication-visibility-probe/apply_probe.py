#!/usr/bin/env python3
"""Add a fork-only pause after managed-Python publication and a native probe."""

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
                if let Some(ref sender) = bytecode_compilation_sender {
"""
if text.count(old) != 1:
    raise SystemExit(
        f"managed publication insertion mismatch: expected 1, found {text.count(old)}"
    )
install.write_text(text.replace(old, new), encoding="utf-8")

tests = root / "crates/uv/tests/python/python_install.rs"
text = tests.read_text(encoding="utf-8")
marker = """#[test]
fn python_reinstall() {
"""
test = r'''#[test]
#[cfg(unix)]
fn python_install_is_discoverable_before_finalization() -> anyhow::Result<()> {
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
    let externally_managed = installation.join("lib/python3.12/EXTERNALLY-MANAGED");
    let marker_absent_while_paused = !externally_managed.exists();

    let find = context
        .python_find()
        .arg("3.12.6")
        .output()
        .context("failed to run concurrent python find")?;

    release.touch()?;
    let install_status = child.wait().context("failed to wait for python install")?;

    assert!(install_status.success());
    assert!(
        find.status.success(),
        "python find failed while the published installation was paused: {}",
        String::from_utf8_lossy(&find.stderr)
    );
    assert!(
        marker_absent_while_paused,
        "EXTERNALLY-MANAGED already existed before command-level finalization"
    );
    assert!(
        externally_managed.exists(),
        "EXTERNALLY-MANAGED was not created after finalization resumed"
    );

    Ok(())
}

'''
if text.count(marker) != 1:
    raise SystemExit(
        f"python install test insertion mismatch: expected 1, found {text.count(marker)}"
    )
tests.write_text(text.replace(marker, test + marker), encoding="utf-8")

print(root)
