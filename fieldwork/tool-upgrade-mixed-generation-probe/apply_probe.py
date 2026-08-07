#!/usr/bin/env python3
"""Add a fork-only late metadata publication failure probe for tool upgrades."""

from pathlib import Path
import sys

root = Path(sys.argv[1])

common = root / "crates/uv/src/commands/tool/common.rs"
text = common.read_text(encoding="utf-8")
old = '''    debug!("Adding receipt for tool `{name}`");
    let tool = Tool::new(
'''
new = '''    if std::env::var_os("UV_INTERNAL__TEST_TOOL_FAIL_BEFORE_METADATA_PUBLISH").is_some() {
        bail!("injected tool upgrade failure before metadata publication");
    }

    debug!("Adding receipt for tool `{name}`");
    let tool = Tool::new(
'''
if text.count(old) != 1:
    raise SystemExit(
        f"tool metadata failpoint insertion mismatch: expected 1, found {text.count(old)}"
    )
common.write_text(text.replace(old, new), encoding="utf-8")

tests = root / "crates/uv/tests/tool/tool_upgrade.rs"
text = tests.read_text(encoding="utf-8")
marker = '''#[test]
fn tool_upgrade_recomputes_relative_exclude_newer() {
'''
test = r'''#[test]
#[cfg(unix)]
fn tool_upgrade_failure_before_metadata_publish_leaves_mixed_generation() -> Result<()> {
    let context = uv_test::test_context!("3.12")
        .with_filtered_counts()
        .with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("babel")
        .arg("--index-url")
        .arg("https://test.pypi.org/simple/")
        .env(EnvVars::UV_PREVIEW_FEATURES, "tool-install-locks")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let receipt = tool_dir.join("babel").join("uv-receipt.toml");
    let lock = tool_dir.join("babel").join("uv.lock");
    let receipt_before = fs_err::read(&receipt)?;
    let lock_before = fs_err::read(&lock)?;

    let failed = context
        .tool_upgrade()
        .arg("babel")
        .arg("--index-url")
        .arg("https://pypi.org/simple/")
        .env(EnvVars::UV_PREVIEW_FEATURES, "tool-install-locks")
        .env("UV_INTERNAL__TEST_TOOL_FAIL_BEFORE_METADATA_PUBLISH", "1")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .output()?;
    assert!(!failed.status.success());
    assert!(
        String::from_utf8_lossy(&failed.stderr)
            .contains("injected tool upgrade failure before metadata publication")
    );

    let python = tool_dir.join("babel").join("bin").join("python");
    let version = Command::new(&python)
        .args([
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('babel'))",
        ])
        .output()?;
    assert!(version.status.success());
    assert_eq!(String::from_utf8_lossy(&version.stdout).trim(), "2.14.0");

    assert_eq!(fs_err::read(&receipt)?, receipt_before);
    assert_eq!(fs_err::read(&lock)?, lock_before);

    context
        .tool_upgrade()
        .arg("babel")
        .arg("--index-url")
        .arg("https://pypi.org/simple/")
        .env(EnvVars::UV_PREVIEW_FEATURES, "tool-install-locks")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    assert_ne!(fs_err::read(&lock)?, lock_before);

    Ok(())
}

'''
if text.count(marker) != 1:
    raise SystemExit(
        f"tool upgrade probe insertion mismatch: expected 1, found {text.count(marker)}"
    )
tests.write_text(text.replace(marker, test + marker), encoding="utf-8")

print(root)
