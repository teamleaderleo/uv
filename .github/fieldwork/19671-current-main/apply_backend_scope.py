#!/usr/bin/env python3
"""Apply the uv_build-only stub-package layout to exact current uv main."""

from __future__ import annotations

from pathlib import Path


SOURCE = Path("crates/uv/src/commands/project/init.rs")


def replace_once(
    text: str, *, name: str, old: str, new: str
) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
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

                // uv_build treats PEP 561 stub packages as type-only distributions and
                // therefore does not have a runtime module to expose as a console script.
                // Other backends retain their existing generated application contract.
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
    print(SOURCE)


if __name__ == "__main__":
    main()
