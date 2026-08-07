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
    /// Return whether the options persisted for an installed tool satisfy the options requested
    /// for a tool invocation.
    ///
    /// Unspecified invocation options inherit the installed tool's settings. Explicit invocation
    /// options must match the corresponding persisted value exactly.
    pub fn satisfies(&self, requested: &Self) -> bool {
        fn field_satisfies<T: PartialEq>(installed: Option<&T>, requested: Option<&T>) -> bool {
            match requested {
                None => true,
                Some(requested) => installed == Some(requested),
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

        field_satisfies(self.index.as_ref(), index.as_ref())
            && field_satisfies(self.index_url.as_ref(), index_url.as_ref())
            && field_satisfies(self.extra_index_url.as_ref(), extra_index_url.as_ref())
            && field_satisfies(self.no_index.as_ref(), no_index.as_ref())
            && field_satisfies(self.find_links.as_ref(), find_links.as_ref())
            && field_satisfies(self.index_strategy.as_ref(), index_strategy.as_ref())
            && field_satisfies(self.keyring_provider.as_ref(), keyring_provider.as_ref())
            && field_satisfies(self.resolution.as_ref(), resolution.as_ref())
            && field_satisfies(self.prerelease.as_ref(), prerelease.as_ref())
            && field_satisfies(self.prerelease_package.as_ref(), prerelease_package.as_ref())
            && field_satisfies(self.fork_strategy.as_ref(), fork_strategy.as_ref())
            && field_satisfies(self.dependency_metadata.as_ref(), dependency_metadata.as_ref())
            && field_satisfies(self.config_settings.as_ref(), config_settings.as_ref())
            && field_satisfies(
                self.config_settings_package.as_ref(),
                config_settings_package.as_ref(),
            )
            && field_satisfies(self.build_isolation.as_ref(), build_isolation.as_ref())
            && field_satisfies(
                self.extra_build_dependencies.as_ref(),
                extra_build_dependencies.as_ref(),
            )
            && field_satisfies(
                self.extra_build_variables.as_ref(),
                extra_build_variables.as_ref(),
            )
            && field_satisfies(self.exclude_newer.as_ref(), exclude_newer.as_ref())
            && field_satisfies(
                self.exclude_newer_package.as_ref(),
                exclude_newer_package.as_ref(),
            )
            && field_satisfies(self.link_mode.as_ref(), link_mode.as_ref())
            && field_satisfies(self.compile_bytecode.as_ref(), compile_bytecode.as_ref())
            && field_satisfies(self.no_sources.as_ref(), no_sources.as_ref())
            && field_satisfies(self.no_sources_package.as_ref(), no_sources_package.as_ref())
            && field_satisfies(self.no_build.as_ref(), no_build.as_ref())
            && field_satisfies(self.no_build_package.as_ref(), no_build_package.as_ref())
            && field_satisfies(self.no_binary.as_ref(), no_binary.as_ref())
            && field_satisfies(self.no_binary_package.as_ref(), no_binary_package.as_ref())
            && field_satisfies(self.torch_backend.as_ref(), torch_backend.as_ref())
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

resolve_path = Path("crates/uv/src/settings.rs")
resolve = resolve_path.read_text()
options_start = '''        let options = resolver_installer_options_with_environment(
            resolver_installer_options(installer, build)?,
            &environment,
        )
'''
if resolve.count(options_start) != 2:
    raise SystemExit("unexpected tool run/install option-construction count")
resolve = resolve.replace(
    options_start,
    options_start.replace("let options =", "let mut options ="),
)
old_torch_block = '''        let filesystem_install_mirrors = filesystem_options
            .map(|options| options.install_mirrors.clone())
            .unwrap_or_default();

        let mut settings = ResolverInstallerSettings::from(options.clone());
        if torch_backend.is_some() {
            settings.resolver.torch_backend = torch_backend;
        }
'''
new_torch_block = '''        if let Some(torch_backend) = torch_backend {
            options.torch_backend = Some(torch_backend);
        }

        let filesystem_install_mirrors = filesystem_options
            .map(|options| options.install_mirrors.clone())
            .unwrap_or_default();

        let settings = ResolverInstallerSettings::from(options.clone());
'''
if resolve.count(old_torch_block) != 2:
    raise SystemExit("unexpected tool run/install torch override count")
resolve = resolve.replace(old_torch_block, new_torch_block)
resolve_path.write_text(resolve)

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
    assert!(output.stderr.is_empty());
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
    assert!(String::from_utf8_lossy(&output.stderr).contains("Resolved"));
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
    assert!(output.stderr.is_empty());
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
    assert!(output.stderr.is_empty());
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
    assert!(String::from_utf8_lossy(&output.stderr).contains("Resolved"));
}

#[test]
fn tool_run_receipt_options_unspecified_torch_backend_inherits() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--torch-backend")
        .arg("cpu")
        .env_remove(EnvVars::UV_TORCH_BACKEND)
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
        .env_remove(EnvVars::UV_TORCH_BACKEND)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(output.stderr.is_empty());
}

#[test]
fn tool_run_receipt_options_same_torch_backend_reuses() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--torch-backend")
        .arg("cpu")
        .env_remove(EnvVars::UV_TORCH_BACKEND)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--torch-backend")
        .arg("cpu")
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_TORCH_BACKEND)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(
        !String::from_utf8_lossy(&output.stderr).contains("Resolved"),
        "same explicit torch backend should reuse installed tool: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn tool_run_receipt_options_conflicting_torch_backend_does_not_reuse() {
    let context = uv_test::test_context!("3.12").with_filtered_exe_suffix();
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    context
        .tool_install()
        .arg("black==24.2.0")
        .arg("--torch-backend")
        .arg("cpu")
        .env_remove(EnvVars::UV_TORCH_BACKEND)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .success();

    let output = context
        .tool_run()
        .arg("--torch-backend")
        .arg("cu126")
        .arg("--from")
        .arg("black==24.2.0")
        .arg("black")
        .arg("--version")
        .env_remove(EnvVars::UV_TORCH_BACKEND)
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .output()
        .unwrap();

    assert!(output.status.success(), "tool run failed: {output:?}");
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("Resolved"),
        "conflicting explicit torch backend should bypass installed tool: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}
'''

test_path.write_text(tests)
