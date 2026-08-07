#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

path = Path("crates/uv/tests/tool/tool_run.rs")
content = path.read_text()
marker = "fn tool_run_receipt_options_unspecified_should_reuse()"
if marker in content:
    raise SystemExit("probe tests already present")

content += r'''

#[test]
fn tool_run_receipt_options_unspecified_should_reuse() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(
        output.stderr.is_empty(),
        "expected installed tool reuse with unspecified run options, got stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn tool_run_receipt_options_same_explicit_reuses() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(
        output.stderr.is_empty(),
        "expected installed tool reuse for the same explicit option, got stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn tool_run_receipt_options_conflicting_explicit_does_not_reuse() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--exclude-newer")
        .arg("2024-03-25T00:00:00Z")
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("Resolved"),
        "expected an explicit conflicting option to bypass the installed environment, got stderr: {stderr}"
    );
}

#[test]
fn tool_run_receipt_options_same_list_value_reuses() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");
    let links = context.temp_dir.child("links");
    links.create_dir_all().unwrap();

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .arg("--find-links")
        .arg(links.as_os_str())
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--exclude-newer")
        .arg("2024-03-01T00:00:00Z")
        .arg("--find-links")
        .arg(links.as_os_str())
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_EXCLUDE_NEWER)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(
        output.stderr.is_empty(),
        "expected identical list-valued options to preserve installed-tool reuse, got stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}
'''

path.write_text(content)
