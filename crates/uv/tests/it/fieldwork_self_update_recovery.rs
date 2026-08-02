#![cfg(windows)]

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use assert_fs::prelude::*;
use serde_json::json;
use wiremock::matchers::{method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

use uv_static::EnvVars;
use uv_test::get_bin;

fn previous_executable_path(path: &Path) -> PathBuf {
    let mut previous: OsString = path.as_os_str().to_os_string();
    previous.push(".previous.exe");
    PathBuf::from(previous)
}

#[tokio::test]
async fn fieldwork_custom_ghe_interruption_displaces_canonical_executable() -> Result<()> {
    let temp = assert_fs::TempDir::new()?;
    let install_dir = temp.child("install");
    install_dir.create_dir_all()?;
    let installed_uv = install_dir.child("uv.exe");
    std::fs::copy(get_bin!(), installed_uv.path()).context("copy test uv executable")?;

    let receipt_dir = temp.child("receipt");
    receipt_dir.create_dir_all()?;
    receipt_dir.child("uv-receipt.json").write_str(&serde_json::to_string_pretty(&json!({
        "install_prefix": install_dir.path(),
        "binaries": ["uv"],
        "cdylibs": [],
        "source": {
            "release_type": "github",
            "owner": "astral-sh",
            "name": "uv",
            "app_name": "uv"
        },
        "version": "0.0.1",
        "provider": {
            "source": "cargo-dist",
            "version": "0.31.0"
        },
        "modify_path": true
    }))?)?;

    let server = MockServer::start().await;
    let target_version = "9.9.9";
    let installer_name = "uv-installer.ps1";
    let started_path = temp.child("installer-started");
    let finish_path = temp.child("finish-installer");

    Mock::given(method("GET"))
        .and(path(format!(
            "/api/v3/repos/astral-sh/uv/releases/tags/{target_version}"
        )))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "tag_name": target_version,
            "name": target_version,
            "url": format!("{}/repos/astral-sh/uv/releases/tags/{target_version}", server.uri()),
            "assets": [{
                "url": format!("{}/assets/{installer_name}", server.uri()),
                "browser_download_url": format!("{}/downloads/{installer_name}", server.uri()),
                "name": installer_name
            }],
            "prerelease": false
        })))
        .mount(&server)
        .await;

    let script = format!(
        "New-Item -ItemType File -Force -Path '{}' | Out-Null\nwhile (-not (Test-Path -LiteralPath '{}')) {{ Start-Sleep -Milliseconds 10 }}\n",
        started_path.path().display(),
        finish_path.path().display(),
    );
    Mock::given(method("GET"))
        .and(path(format!("/downloads/{installer_name}")))
        .respond_with(ResponseTemplate::new(200).set_body_string(script))
        .mount(&server)
        .await;

    // Do not let the deliberately orphanable installer inherit the test runner's
    // output handles. Otherwise the product assertion can pass while the workflow
    // remains alive waiting for a descendant to close those handles.
    let mut child = Command::new(installed_uv.path())
        .args(["self", "update", target_version])
        .env("AXOUPDATER_CONFIG_PATH", receipt_dir.path())
        .env(EnvVars::UV_INSTALLER_GHE_BASE_URL, server.uri())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .context("launch copied uv through custom updater route")?;

    for _ in 0..600 {
        if started_path.exists() {
            break;
        }
        if let Some(status) = child.try_wait()? {
            bail!("uv exited before the installer started: {status}");
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    if !started_path.exists() {
        let _ = child.kill();
        bail!("custom installer did not start");
    }

    let canonical = installed_uv.path();
    let previous = previous_executable_path(canonical);
    assert!(
        !canonical.exists(),
        "axoupdater custom route should have displaced the canonical executable before the installer"
    );
    assert!(
        previous.exists(),
        "axoupdater custom route should retain the running executable as .previous.exe"
    );

    child.kill().context("interrupt copied uv process")?;
    // Release the deliberately blocked installer immediately so no descendant is
    // left behind after the uv parent has been interrupted.
    finish_path.write_str("finish")?;
    let _ = child.wait();

    tokio::time::sleep(Duration::from_millis(250)).await;
    assert!(
        !canonical.exists(),
        "process interruption bypasses axoupdater's ordinary error restoration"
    );
    assert!(
        previous.exists(),
        "the recoverable previous executable remains under a noncanonical name"
    );

    std::fs::rename(&previous, canonical).context("restore characterized test executable")?;
    Ok(())
}
