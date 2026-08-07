#!/usr/bin/env python3
"""Add a Unix characterization test for tool-uninstall entrypoint residue."""

from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv/tests/tool/tool_uninstall.rs"
text = path.read_text(encoding="utf-8")

old_import = "use assert_cmd::assert::OutputAssertExt;\n"
new_import = "use std::process::Command;\n\n" + old_import
if text.count(old_import) != 1:
    raise SystemExit("tool_uninstall import insertion point mismatch")
text = text.replace(old_import, new_import)

old = r'''#[test]
fn tool_uninstall_all_missing_receipt() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    // Install `black`
    context
        .tool_install()
        .arg("black==24.2.0")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .assert()
        .success();

    fs_err::remove_file(tool_dir.join("black").join("uv-receipt.toml")).unwrap();

    uv_snapshot!(context.filters(), context.tool_uninstall().arg("--all")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str()), @"
    exit_code: 0 (success)
    ----- stderr -----
    Removed dangling environment for `black`
    ");
}
'''
new = r'''#[test]
fn tool_uninstall_all_missing_receipt() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    // Install `black`
    context
        .tool_install()
        .arg("black==24.2.0")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .assert()
        .success();

    fs_err::remove_file(tool_dir.join("black").join("uv-receipt.toml")).unwrap();

    uv_snapshot!(context.filters(), context.tool_uninstall().arg("--all")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str()), @"
    exit_code: 0 (success)
    ----- stderr -----
    Removed dangling environment for `black`
    ");
}

#[test]
#[cfg(unix)]
fn tool_uninstall_all_missing_receipt_leaves_entrypoint_residue() -> anyhow::Result<()> {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let black = bin_dir.join("black");
    let blackd = bin_dir.join("blackd");
    assert!(fs_err::symlink_metadata(&black).is_ok());
    assert!(fs_err::symlink_metadata(&blackd).is_ok());

    fs_err::remove_file(tool_dir.join("black").join("uv-receipt.toml"))?;

    context
        .tool_uninstall()
        .arg("--all")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .assert()
        .success();

    assert!(!tool_dir.join("black").exists());
    assert!(
        fs_err::symlink_metadata(&black).is_ok(),
        "public black entrypoint path was removed despite missing receipt"
    );
    assert!(
        fs_err::symlink_metadata(&blackd).is_ok(),
        "public blackd entrypoint path was removed despite missing receipt"
    );
    assert!(
        Command::new(&black).arg("--version").output().is_err(),
        "dangling black entrypoint unexpectedly remained executable"
    );

    context
        .tool_install()
        .arg("black==24.2.0")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let recovered = Command::new(&black).arg("--version").output()?;
    assert!(recovered.status.success());

    Ok(())
}
'''
if text.count(old) != 1:
    raise SystemExit(
        f"missing-receipt test block mismatch: expected 1, found {text.count(old)}"
    )
path.write_text(text.replace(old, new), encoding="utf-8")
print(path)
