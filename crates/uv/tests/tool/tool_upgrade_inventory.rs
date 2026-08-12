use anyhow::Result;
use assert_fs::prelude::*;
use predicates::prelude::*;

use uv_static::EnvVars;

#[test]
fn tool_upgrade_all_propagates_invalid_inventory_name() -> Result<()> {
    let context = uv_test::test_context!("3.12");
    let tool_dir = context.temp_dir.child("tools");
    let bin_dir = context.temp_dir.child("bin");

    tool_dir.create_dir_all()?;
    tool_dir
        .child("not a valid package name!")
        .create_dir_all()?;

    context
        .tool_upgrade()
        .arg("--all")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str())
        .env(EnvVars::XDG_BIN_HOME, bin_dir.as_os_str())
        .env(EnvVars::PATH, bin_dir.as_os_str())
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("Not a valid package")
                .and(predicate::str::contains("Nothing to upgrade").not()),
        );

    Ok(())
}
