#!/usr/bin/env python3
"""Limit the public stubs-package policy to uv_build.

The public candidate fixes uv_build, but applies its hyphenated stub-only
layout and console-script suppression to every backend. This transformation
keeps those two choices behind the uv_build backend boundary.
"""

from __future__ import annotations

from pathlib import Path


SOURCE = Path("crates/uv/src/commands/project/init.rs")


def replace_span(text: str, *, name: str, start: str, end: str, replacement: str) -> str:
    start_count = text.count(start)
    end_count = text.count(end)
    if start_count != 1 or end_count != 1:
        raise SystemExit(
            f"{name} anchor mismatch: start={start_count}, end={end_count}"
        )
    start_index = text.index(start)
    end_index = text.index(end, start_index) + len(end)
    if end_index <= start_index:
        raise SystemExit(f"{name} anchors are out of order")
    return text[:start_index] + replacement + text[end_index:]


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    script_start = """        // Include additional project configuration for packaged applications
        if package {
"""
    script_end = """            // Add a build system
            let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
"""
    script_replacement = """        // Include additional project configuration for packaged applications
        if package {
            let build_backend = build_backend.unwrap_or(ProjectBuildBackend::Uv);
            let uv_stub_package = build_backend == ProjectBuildBackend::Uv
                && stubs_package_module_dir(name).is_some();

            // uv_build treats PEP 561 stub packages as type-only distributions and
            // therefore does not have a runtime module to expose as a console script.
            // Other backends retain their existing generated application contract.
            if !bare && !uv_stub_package {
                pyproject.push('\n');
                pyproject.push_str(&pyproject_project_scripts(name, name.as_str(), "main"));
            }

            // Add a build system
"""
    text = replace_span(
        text,
        name="packaged-application script policy",
        start=script_start,
        end=script_end,
        replacement=script_replacement,
    )

    layout_start = """    let src_dir = path.join("src");
    let stubs_module_dir = stubs_package_module_dir(package);
"""
    layout_end = """    let pkg_dir = src_dir.join(stubs_module_dir.as_deref().unwrap_or(module_name.as_ref()));
"""
    layout_replacement = """    let src_dir = path.join("src");
    let stubs_module_dir = if build_backend == ProjectBuildBackend::Uv {
        stubs_package_module_dir(package)
    } else {
        None
    };
    let pkg_dir = src_dir.join(stubs_module_dir.as_deref().unwrap_or(module_name.as_ref()));
"""
    text = replace_span(
        text,
        name="generated package layout",
        start=layout_start,
        end=layout_end,
        replacement=layout_replacement,
    )

    SOURCE.write_text(text, encoding="utf-8")
    print(SOURCE)


if __name__ == "__main__":
    main()
