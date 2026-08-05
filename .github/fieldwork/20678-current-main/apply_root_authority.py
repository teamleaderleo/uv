#!/usr/bin/env python3
"""Route reusable workspace-member indexes to the workspace root."""

from __future__ import annotations

from pathlib import Path


SOURCE = Path("crates/uv/src/commands/project/add.rs")
TESTS = Path("crates/uv/tests/project/edit.rs")


def replace_once(text: str, *, name: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    source = replace_once(
        source,
        name="index ownership",
        old='''    // Add any indexes that were provided on the command-line, in priority order.
    if !raw {
        let root_dir = match &target {
            AddTarget::Script(_, _) => CWD.as_path(),
            AddTarget::Project(project, _) => project.root(),
        };
        let locations = IndexLocations::new(indexes, Vec::new(), false);
        let mut indexes = locations.defined_indexes().collect::<Vec<_>>();
        indexes.reverse();
        for index in indexes {
            toml.add_index(index, root_dir)?;
        }
    }
''',
        new='''    // General workspace search configuration belongs to the workspace root. A single
    // named index remains with the selected member because the added requirements are pinned to
    // it through `tool.uv.sources` and the index is therefore package-specific.
    let mut workspace_index_content = None;
    if !raw {
        // `index` borrows from the original vector. Snapshot the routing decision before the
        // validated indexes are consumed below, so no borrow survives the move.
        let route_indexes_to_workspace_root = index.is_none();
        let locations = IndexLocations::new(indexes, Vec::new(), false);
        let mut indexes = locations.defined_indexes().collect::<Vec<_>>();
        indexes.reverse();

        if let AddTarget::Project(project, _) = &target
            && route_indexes_to_workspace_root
            && project.workspace().install_path() != project.root()
        {
            let workspace = project.workspace();
            let mut workspace_toml = PyProjectTomlMut::from_toml(
                &workspace.pyproject_toml().raw,
                DependencyTarget::PyProjectToml,
            )?;
            for index in indexes {
                workspace_toml.add_index(index, workspace.install_path())?;
            }
            let content = workspace_toml.to_string();
            if content != workspace.pyproject_toml().raw.as_str() {
                workspace_index_content = Some(content);
            }
        } else {
            let root_dir = match &target {
                AddTarget::Script(_, _) => CWD.as_path(),
                AddTarget::Project(project, _) => project.root(),
            };
            for index in indexes {
                toml.add_index(index, root_dir)?;
            }
        }
    }
''',
    )

    source = replace_once(
        source,
        name="dual-file write",
        old='''    let content = toml.to_string();

    // Save the modified `pyproject.toml` or script.
    modified |= target.write(&content)?;
''',
        new='''    let content = toml.to_string();
    let workspace_indexes_modified = workspace_index_content.is_some();

    // Save the dependency target and, when needed, the workspace index owner. If either write
    // fails, restore the member, workspace root, and lockfile snapshot.
    let write_result = (|| -> Result<bool, io::Error> {
        let mut changed = target.write(&content)?;
        if let Some(workspace_content) = workspace_index_content.as_deref() {
            let AddTarget::Project(project, _) = &target else {
                unreachable!("only project targets can update workspace index configuration")
            };
            fs_err::write(
                project.workspace().install_path().join("pyproject.toml"),
                workspace_content,
            )?;
            changed = true;
        }
        Ok(changed)
    })();
    modified |= match write_result {
        Ok(changed) => changed,
        Err(err) => {
            let _ = snapshot.revert();
            return Err(err.into());
        }
    };
''',
    )

    source = replace_once(
        source,
        name="workspace rediscovery",
        old='''    // Update the `pypackage.toml` in-memory.
    let target = target.update(&content, &WorkspaceCache::default())?;
''',
        new='''    // Update the project in memory. A workspace-root edit requires full rediscovery;
    // updating only the selected member would leave stale workspace configuration.
    let target = if workspace_indexes_modified {
        let AddTarget::Project(project, python_target) = target else {
            unreachable!("only project targets can update workspace index configuration")
        };
        let project_root = project.root().to_path_buf();
        match VirtualProject::discover(
            &project_root,
            &DiscoveryOptions::default(),
            cache,
            &WorkspaceCache::default(),
        )
        .await
        {
            Ok(project) => AddTarget::Project(project, python_target),
            Err(err) => {
                if modified {
                    let _ = snapshot.revert();
                }
                return Err(err.into());
            }
        }
    } else {
        match target.update(&content, &WorkspaceCache::default()) {
            Ok(target) => target,
            Err(err) => {
                if modified {
                    let _ = snapshot.revert();
                }
                return Err(err.into());
            }
        }
    };
''',
    )

    SOURCE.write_text(source, encoding="utf-8")

    tests = TESTS.read_text(encoding="utf-8")
    anchor = """/// Add a path dependency, which should be implicitly added to the workspace.
#[test]
fn add_path_implicit_workspace() -> Result<()> {
"""
    inserted = r'''#[test]
fn add_implicit_index_to_workspace_member_updates_root() -> Result<()> {
    let context = uv_test::test_context!("3.12");

    let workspace = context.temp_dir.child("workspace");
    workspace.child("pyproject.toml").write_str(indoc! {r#"
        [tool.uv.workspace]
        members = ["child"]
    "#})?;

    let child = workspace.child("child");
    child.child("pyproject.toml").write_str(indoc! {r#"
        [project]
        name = "child"
        version = "0.1.0"
        requires-python = ">=3.12"
        dependencies = []
    "#})?;

    context
        .add()
        .current_dir(workspace.path())
        .arg("--package")
        .arg("child")
        .arg("--frozen")
        .arg("--index")
        .arg("https://example.com/simple")
        .arg("anyio")
        .assert()
        .success();

    let root_pyproject = fs_err::read_to_string(workspace.join("pyproject.toml"))?;
    assert_snapshot!(root_pyproject, @r#"
    [tool.uv.workspace]
    members = ["child"]

    [[tool.uv.index]]
    url = "https://example.com/simple"
    "#);

    let child_pyproject = fs_err::read_to_string(child.join("pyproject.toml"))?;
    assert_snapshot!(child_pyproject, @r#"
    [project]
    name = "child"
    version = "0.1.0"
    requires-python = ">=3.12"
    dependencies = [
        "anyio",
    ]
    "#);

    Ok(())
}

#[test]
fn add_named_index_to_workspace_member_keeps_source_local() -> Result<()> {
    let context = uv_test::test_context!("3.12");

    let workspace = context.temp_dir.child("workspace");
    workspace.child("pyproject.toml").write_str(indoc! {r#"
        [tool.uv.workspace]
        members = ["child"]
    "#})?;

    let child = workspace.child("child");
    child.child("pyproject.toml").write_str(indoc! {r#"
        [project]
        name = "child"
        version = "0.1.0"
        requires-python = ">=3.12"
        dependencies = []
    "#})?;

    context
        .add()
        .current_dir(workspace.path())
        .arg("--package")
        .arg("child")
        .arg("--frozen")
        .arg("--index")
        .arg("internal=https://example.com/simple")
        .arg("anyio")
        .assert()
        .success();

    let root_pyproject = fs_err::read_to_string(workspace.join("pyproject.toml"))?;
    assert_snapshot!(root_pyproject, @r#"
    [tool.uv.workspace]
    members = ["child"]
    "#);

    let child_pyproject = fs_err::read_to_string(child.join("pyproject.toml"))?;
    assert_snapshot!(child_pyproject, @r#"
    [project]
    name = "child"
    version = "0.1.0"
    requires-python = ">=3.12"
    dependencies = [
        "anyio",
    ]

    [tool.uv.sources]
    anyio = { index = "internal" }

    [[tool.uv.index]]
    name = "internal"
    url = "https://example.com/simple"
    "#);

    Ok(())
}

'''
    tests = replace_once(
        tests,
        name="integration test insertion",
        old=anchor,
        new=inserted + anchor,
    )
    TESTS.write_text(tests, encoding="utf-8")

    print(SOURCE)
    print(TESTS)


if __name__ == "__main__":
    main()
