#!/usr/bin/env python3
"""Apply the bounded backend-scope repair for astral-sh/uv#19671.

The exact public candidate fixes the uv_build contract but applies its
hyphenated stub-only layout and console-script suppression to every backend.
This runner-local transformation limits both decisions to uv_build while
leaving every other backend on its prior generated layout.
"""

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    source = Path("crates/uv/src/commands/project/init.rs")

    replace_once(
        source,
        '''        // Include additional project configuration for packaged applications
        if package {
            // Since it'll be packaged, we can add a `[project.scripts]` entry.
            //
            // PEP 561 stub packages are type-only distributions, so they
            // should not declare a console script for a runtime module.
            if !bare && stubs_package_module_dir(name).is_none() {
                pyproject.push('\n');
                pyproject.push_str(&pyproject_project_scripts(name, name.as_str(), "main"));
            }

            // Add a build system
            let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
''',
        '''        // Include additional project configuration for packaged applications
        if package {
            let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
            let uv_stub_package = build_backend == ProjectBuildBackend::Uv
                && stubs_package_module_dir(name).is_some();

            // uv_build treats PEP 561 stub packages as type-only distributions and
            // therefore does not have a runtime module to expose as a console script.
            // Other backends retain their existing generated application contract until
            // they have an explicit stub-only layout of their own.
            if !bare && !uv_stub_package {
                pyproject.push('\n');
                pyproject.push_str(&pyproject_project_scripts(name, name.as_str(), "main"));
            }

            // Add a build system
''',
    )

    replace_once(
        source,
        '''    let src_dir = path.join("src");
    let stubs_module_dir = stubs_package_module_dir(package);
    let pkg_dir = src_dir.join(stubs_module_dir.as_deref().unwrap_or(module_name.as_ref()));
''',
        '''    let src_dir = path.join("src");
    let stubs_module_dir = if build_backend == ProjectBuildBackend::Uv {
        stubs_package_module_dir(package)
    } else {
        None
    };
    let pkg_dir = src_dir.join(stubs_module_dir.as_deref().unwrap_or(module_name.as_ref()));
''',
    )

    print(source)


if __name__ == "__main__":
    main()
