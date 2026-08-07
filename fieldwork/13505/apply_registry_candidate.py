#!/usr/bin/env python3
"""Apply the uv #13505 PATH+registry discriminator and retained candidate.

The baseline receives only the registry-backed integration test. The candidate
also receives the ordinal case-insensitive final-list repair from
`apply_candidate.py`; the earlier duplicated-PATH control is intentionally not
applied here because it does not reproduce the public issue shape.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import apply_candidate as retained


def apply_registry_test(root: Path) -> None:
    path = root / "crates/uv/tests/python/python_list.rs"
    marker = """#[test]
fn python_list_downloads() {
"""
    block = r'''#[cfg(all(windows, feature = "test-windows-registry"))]
#[test]
fn python_list_deduplicates_case_variant_registry_and_path_entries() -> Result<()> {
    use std::ffi::OsString;
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use std::process::Command;

    struct RegistryCleanup(String);

    impl Drop for RegistryCleanup {
        fn drop(&mut self) {
            let _ = Command::new("reg.exe")
                .arg("delete")
                .arg(&self.0)
                .arg("/f")
                .output();
        }
    }

    fn run_reg(command: &mut Command) -> Result<()> {
        let output = command.output()?;
        if output.status.success() {
            return Ok(());
        }
        anyhow::bail!(
            "registry command failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    let context = uv_test::test_context_with_versions!(&["3.12"])
        .with_filtered_python_symlinks()
        .with_filtered_python_keys()
        .with_collapsed_whitespace();
    let search_path = context.python_path();

    let executable = std::env::split_paths(&search_path)
        .find_map(|dir| {
            ["python3.12.exe", "python3.exe", "python.exe"]
                .into_iter()
                .map(|name| dir.join(name))
                .find(|candidate| candidate.is_file())
        })
        .ok_or_else(|| anyhow::anyhow!("test Python executable was not found in the controlled search path"))?;

    let original_wide = executable.as_os_str().encode_wide().collect::<Vec<_>>();
    let mut variant_wide = original_wide.clone();
    let mut changed = false;
    // Skip the drive prefix and flip one ordinary ASCII code unit. This keeps
    // the path on the same case-insensitive Windows file while guaranteeing a
    // distinct queried spelling for the final-list boundary.
    for unit in variant_wide.iter_mut().skip(3) {
        if (*unit >= b'a' as u16) && (*unit <= b'z' as u16) {
            *unit -= (b'a' - b'A') as u16;
            changed = true;
            break;
        }
        if (*unit >= b'A' as u16) && (*unit <= b'Z' as u16) {
            *unit += (b'a' - b'A') as u16;
            changed = true;
            break;
        }
    }
    anyhow::ensure!(changed, "test Python path has no ASCII component to case-flip");
    anyhow::ensure!(original_wide != variant_wide, "registry path spelling was not changed");

    let registry_executable = std::path::PathBuf::from(OsString::from_wide(&variant_wide));
    anyhow::ensure!(
        registry_executable.is_file(),
        "case-varied registry path does not resolve to the test Python: {}",
        registry_executable.display()
    );

    let company_root = format!(
        r"HKCU\Software\Python\UvFieldwork13505_{}",
        std::process::id()
    );
    let tag_key = format!(r"{}\3.12", company_root);
    let install_key = format!(r"{}\InstallPath", tag_key);
    let cleanup = RegistryCleanup(company_root.clone());

    let mut sys_version = Command::new("reg.exe");
    sys_version
        .arg("add")
        .arg(&tag_key)
        .args(["/v", "SysVersion", "/t", "REG_SZ", "/d", "3.12", "/f"]);
    run_reg(&mut sys_version)?;

    let mut executable_path = Command::new("reg.exe");
    executable_path
        .arg("add")
        .arg(&install_key)
        .args(["/v", "ExecutablePath", "/t", "REG_SZ", "/d"])
        .arg(registry_executable.as_os_str())
        .arg("/f");
    run_reg(&mut executable_path)?;

    let output = context
        .python_list()
        .arg("3.12")
        .arg("--only-installed")
        .env(EnvVars::UV_PYTHON_SEARCH_PATH, &search_path)
        .env(EnvVars::UV_PYTHON_NO_REGISTRY, "false")
        .output()?;

    // Explicit cleanup happens before product assertions so panic-abort test
    // profiles do not leave our temporary HKCU company behind on assertion
    // failure. The Drop guard remains as a best-effort path for early Result
    // returns above.
    let cleanup_output = Command::new("reg.exe")
        .arg("delete")
        .arg(&company_root)
        .arg("/f")
        .output()?;
    std::mem::forget(cleanup);
    anyhow::ensure!(
        cleanup_output.status.success(),
        "failed to remove temporary registry company: {}",
        String::from_utf8_lossy(&cleanup_output.stderr)
    );

    assert!(
        output.status.success(),
        "uv python list failed:\n{}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let needle = executable.to_string_lossy().to_ascii_lowercase();
    let matching = stdout
        .lines()
        .filter(|line| line.to_ascii_lowercase().contains(&needle))
        .count();

    assert_eq!(
        matching,
        1,
        "expected one final-list row for PATH/registry case variants of {}; stdout:\n{}",
        executable.display(),
        stdout
    );

    Ok(())
}

'''
    retained.replace_once(path, marker, block + marker, "PATH+registry integration control")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    apply_registry_test(root)
    if not args.tests_only:
        retained.apply_candidate(root)


if __name__ == "__main__":
    main()
