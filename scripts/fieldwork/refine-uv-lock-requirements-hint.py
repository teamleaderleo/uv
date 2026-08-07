#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

# The carrier applies this refinement after fetching exact public uv base
# b358fb6fce199fb1977913d310ddb6d573e44031 from astral-sh/uv.
# The base workflow compares immutable PR base and head SHAs directly.
# Rust 1.97.1 rustfmt and clippy are installed explicitly by the carrier.
# The accepted pip-specific hint path is retained while the generic collector
# is extended for command paths that render through the shared error chain.
# Applied source is unstaged before the eight-file exact-diff fence.


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement anchor, found {count}")
    path.write_text(content.replace(old, new, 1))


diagnostics = Path("crates/uv/src/commands/diagnostics.rs")
anchor = "        collect_hint::<ExtrasWithoutSourceError>(cause, &mut hints);\n"
replace_once(
    diagnostics,
    anchor,
    anchor
    + "        collect_hint::<uv_requirements::UvLockfileAsRequirementsError>(cause, &mut hints);\n",
)

tool_tests = Path("crates/uv/tests/tool/tool_run.rs")
tool_tests.write_text(
    tool_tests.read_text()
    + r'''

#[test]
fn tool_run_with_requirements_has_dedicated_hint() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    context.temp_dir.child("pyproject.toml").write_str(
        r#"
        [project]
        name = "project"
        version = "0.1.0"
        requires-python = ">=3.12"
        dependencies = []
        "#,
    )?;
    context.lock().assert().success();

    context
        .tool_run()
        .arg("--with-requirements")
        .arg("uv.lock")
        .arg("ruff")
        .assert()
        .failure()
        .stderr(predicates::str::contains(
            "The file `uv.lock` appears to be a uv lockfile",
        ))
        .stderr(predicates::str::contains(
            "\nhint: Use `uv sync` or `uv export --format requirements-txt` from the owning project",
        ));

    Ok(())
}
'''
)
