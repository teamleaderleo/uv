#!/usr/bin/env python3
"""Apply the bounded tool-upgrade inventory enumeration repair."""

from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(path: Path, old: str, new: str, *, name: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{name} mismatch in {path}: expected 1, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


replace(
    root / "crates/uv/src/commands/tool/upgrade.rs",
    """            installed_tools
                .tools()
                .unwrap_or_default()
                .into_iter()
""",
    """            installed_tools
                .tools()?
                .into_iter()
""",
    name="all-tools enumeration",
)

path = root / "crates/uv/tests/tool/tool_upgrade.rs"
text = path.read_text(encoding="utf-8")
marker = """#[test]
fn tool_upgrade_preserves_workspace_member_editability() -> Result<()> {
"""
test = r"""#[test]
fn tool_upgrade_all_fails_on_invalid_tool_directory() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    tool_dir.create_dir_all()?;
    tool_dir.child("not a valid package name!").create_dir_all()?;

    context
        .tool_upgrade()
        .arg("--all")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .failure();

    Ok(())
}

"""
if text.count(marker) != 1:
    raise SystemExit("tool-upgrade test insertion point mismatch")
path.write_text(text.replace(marker, test + marker), encoding="utf-8")
print(root)
