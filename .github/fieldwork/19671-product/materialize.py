#!/usr/bin/env python3
"""Materialize the uv_build-only stub package repair and native tests."""

from __future__ import annotations

from pathlib import Path

SOURCE = Path("crates/uv/src/commands/project/init.rs")
TESTS = Path("crates/uv/tests/project/init.rs")


def replace_once(text: str, *, name: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    text = replace_once(
        text,
        name="application script policy",
        old=r'''            Self::ApplicationWithLibrary => {
                // Since it'll be packaged, we can add a `[project.scripts]` entry
                pyproject.push('\n');
                pyproject.push_str(&pyproject_project_scripts(name, name.as_str(), "main"));

                // Add a build system
                let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
''',
        new=r'''            Self::ApplicationWithLibrary => {
                let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
                let uv_stub_package = build_backend == ProjectBuildBackend::Uv
                    && stubs_package_module_dir(name).is_some();

                // Since it'll be packaged, we can add a `[project.scripts]` entry.
                //
                // uv_build treats PEP 561 stub packages as type-only distributions, so they
                // do not have a runtime module to expose as a console script. Other backends
                // retain their existing generated application contract.
                if !uv_stub_package {
                    pyproject.push('\n');
                    pyproject.push_str(&pyproject_project_scripts(name, name.as_str(), "main"));
                }

                // Add a build system
''',
    )

    text = replace_once(
        text,
        name="generated package layout",
        old='''    let module_name = package.as_dist_info_name();

    let src_dir = path.join("src");
    let pkg_dir = src_dir.join(&*module_name);
    fs_err::create_dir_all(&pkg_dir)?;
''',
        new='''    let module_name = package.as_dist_info_name();

    let src_dir = path.join("src");
    let stubs_module_dir = if build_backend == ProjectBuildBackend::Uv {
        stubs_package_module_dir(package)
    } else {
        None
    };
    let pkg_dir = src_dir.join(stubs_module_dir.as_deref().unwrap_or(module_name.as_ref()));
    fs_err::create_dir_all(&pkg_dir)?;

    if stubs_module_dir.is_some() {
        let init_pyi = pkg_dir.join("__init__.pyi");
        if !init_pyi.try_exists()? {
            fs_err::write(init_pyi, "")?;
        }
        return Ok(());
    }
''',
    )

    text = replace_once(
        text,
        name="stub module helper",
        old='''#[derive(Debug, Clone)]
enum GitDiscoveryResult {
''',
        new='''fn stubs_package_module_dir(package: &PackageName) -> Option<String> {
    package
        .as_dist_info_name()
        .strip_suffix("_stubs")
        .map(|stem| format!("{stem}-stubs"))
}

#[derive(Debug, Clone)]
enum GitDiscoveryResult {
''',
    )

    SOURCE.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")

    tests = r'''/// Test that stub-only packages use the PEP 561 layout with uv_build.
#[test]
fn init_package_stubs_uv_backend() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let child = context.temp_dir.child("foo-stubs");
    child.create_dir_all()?;

    context
        .init()
        .current_dir(&child)
        .arg("--package")
        .assert()
        .success();

    child
        .child("src/foo-stubs/__init__.pyi")
        .assert(predicate::path::is_file());
    child
        .child("src/foo_stubs/__init__.py")
        .assert(predicate::path::missing());

    let pyproject = fs_err::read_to_string(child.join("pyproject.toml"))?;
    assert!(!pyproject.contains("[project.scripts]"));
    assert!(pyproject.contains("build-backend = \"uv_build\""));

    context.build().current_dir(&child).assert().success();

    Ok(())
}

/// Test that third-party backends retain their existing package layout and script contract.
#[test]
fn init_package_stubs_hatch_backend() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let child = context.temp_dir.child("foo-stubs");
    child.create_dir_all()?;

    context
        .init()
        .current_dir(&child)
        .arg("--package")
        .arg("--build-backend")
        .arg("hatch")
        .assert()
        .success();

    child
        .child("src/foo_stubs/__init__.py")
        .assert(predicate::path::is_file());
    child
        .child("src/foo-stubs/__init__.pyi")
        .assert(predicate::path::missing());

    let pyproject = fs_err::read_to_string(child.join("pyproject.toml"))?;
    assert!(pyproject.contains("[project.scripts]"));
    assert!(pyproject.contains("build-backend = \"hatchling.build\""));

    Ok(())
}

/// Test that third-party libraries remain script-free and use their normal module layout.
#[test]
fn init_library_stubs_hatch_backend() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let child = context.temp_dir.child("foo-stubs");
    child.create_dir_all()?;

    context
        .init()
        .current_dir(&child)
        .arg("--lib")
        .arg("--build-backend")
        .arg("hatch")
        .assert()
        .success();

    child
        .child("src/foo_stubs/__init__.py")
        .assert(predicate::path::is_file());
    child
        .child("src/foo-stubs/__init__.pyi")
        .assert(predicate::path::missing());

    let pyproject = fs_err::read_to_string(child.join("pyproject.toml"))?;
    assert!(!pyproject.contains("[project.scripts]"));
    assert!(pyproject.contains("build-backend = \"hatchling.build\""));

    Ok(())
}

'''

    text = replace_once(
        text,
        name="native regression tests",
        old="#[test]\nfn init_bare_lib() {\n",
        new=tests + "#[test]\nfn init_bare_lib() {\n",
    )

    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_source()
    patch_tests()
    print(SOURCE)
    print(TESTS)


if __name__ == "__main__":
    main()
