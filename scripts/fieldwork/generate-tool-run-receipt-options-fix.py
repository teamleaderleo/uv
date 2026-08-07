#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

settings_path = Path("crates/uv-settings/src/settings.rs")
settings = settings_path.read_text()
wire_marker = "\n/// The on-disk representation of [`ToolOptions`] in a tool receipt.\n"
if settings.count(wire_marker) != 1:
    raise SystemExit("unexpected ToolOptions wire marker count")
if "pub fn satisfies(&self, requested: &Self)" in settings:
    raise SystemExit("ToolOptions::satisfies already present")

implementation = r'''

impl ToolOptions {
    /// Return whether the options persisted for an installed tool satisfy the explicit options
    /// requested for a tool invocation.
    ///
    /// Unspecified invocation options inherit the installed tool's settings. Explicit invocation
    /// options must match the corresponding persisted value exactly.
    pub fn satisfies(&self, requested: &Self) -> bool {
        fn field_satisfies<T: PartialEq>(installed: &Option<T>, requested: &Option<T>) -> bool {
            match requested {
                None => true,
                Some(requested) => installed.as_ref() == Some(requested),
            }
        }

        let Self {
            index,
            index_url,
            extra_index_url,
            no_index,
            find_links,
            index_strategy,
            keyring_provider,
            resolution,
            prerelease,
            prerelease_package,
            fork_strategy,
            dependency_metadata,
            config_settings,
            config_settings_package,
            build_isolation,
            extra_build_dependencies,
            extra_build_variables,
            exclude_newer,
            exclude_newer_package,
            link_mode,
            compile_bytecode,
            no_sources,
            no_sources_package,
            no_build,
            no_build_package,
            no_binary,
            no_binary_package,
            torch_backend,
        } = requested;

        field_satisfies(&self.index, index)
            && field_satisfies(&self.index_url, index_url)
            && field_satisfies(&self.extra_index_url, extra_index_url)
            && field_satisfies(&self.no_index, no_index)
            && field_satisfies(&self.find_links, find_links)
            && field_satisfies(&self.index_strategy, index_strategy)
            && field_satisfies(&self.keyring_provider, keyring_provider)
            && field_satisfies(&self.resolution, resolution)
            && field_satisfies(&self.prerelease, prerelease)
            && field_satisfies(&self.prerelease_package, prerelease_package)
            && field_satisfies(&self.fork_strategy, fork_strategy)
            && field_satisfies(&self.dependency_metadata, dependency_metadata)
            && field_satisfies(&self.config_settings, config_settings)
            && field_satisfies(&self.config_settings_package, config_settings_package)
            && field_satisfies(&self.build_isolation, build_isolation)
            && field_satisfies(&self.extra_build_dependencies, extra_build_dependencies)
            && field_satisfies(&self.extra_build_variables, extra_build_variables)
            && field_satisfies(&self.exclude_newer, exclude_newer)
            && field_satisfies(&self.exclude_newer_package, exclude_newer_package)
            && field_satisfies(&self.link_mode, link_mode)
            && field_satisfies(&self.compile_bytecode, compile_bytecode)
            && field_satisfies(&self.no_sources, no_sources)
            && field_satisfies(&self.no_sources_package, no_sources_package)
            && field_satisfies(&self.no_build, no_build)
            && field_satisfies(&self.no_build_package, no_build_package)
            && field_satisfies(&self.no_binary, no_binary)
            && field_satisfies(&self.no_binary_package, no_binary_package)
            && field_satisfies(&self.torch_backend, torch_backend)
    }
}
'''
settings = settings.replace(wire_marker, implementation + wire_marker)
settings_path.write_text(settings)

run_path = Path("crates/uv/src/commands/tool/run.rs")
run = run_path.read_text()
old_gate = "ToolOptions::from(options) == *receipt.options()"
new_gate = "receipt.options().satisfies(&ToolOptions::from(options))"
if run.count(old_gate) != 1:
    raise SystemExit("unexpected installed-tool options gate count")
run = run.replace(old_gate, new_gate)
run_path.write_text(run)

test_path = Path("crates/uv/tests/tool/tool_run.rs")
tests = test_path.read_text()
marker = "fn tool_run_receipt_options_unspecified_should_reuse()"
if marker in tests:
    raise SystemExit("receipt option tests already present")

tests += r'''

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

#[test]
fn tool_run_receipt_options_unspecified_fields_inherit() {
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
        "expected unspecified fields to inherit receipt values, got stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn tool_run_receipt_options_isolated_still_bypasses() {
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

    let output = context
        .tool_run()
        .arg("--isolated")
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("Resolved"),
        "expected --isolated to bypass the installed environment, got stderr: {stderr}"
    );
}
'''

test_path.write_text(tests)
