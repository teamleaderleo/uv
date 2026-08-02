from pathlib import Path

path = Path("crates/uv/src/commands/self_update.rs")
text = path.read_text(encoding="utf-8")

signature = '''async fn execute_official_installer(
    installer_path: &Path,
    install_prefix: &Path,
    modify_path: bool,
    target_version: &Pep440Version,
    astral_mirror_url: Option<&str>,
    installer_config_path: Option<&Path>,
) -> Result<(), AxoupdateError> {'''

replacement = '''async fn execute_official_installer(
    installer_path: &Path,
    install_prefix: &Path,
    modify_path: bool,
    target_version: &Pep440Version,
    astral_mirror_url: Option<&str>,
    installer_config_path: Option<&Path>,
) -> Result<(), AxoupdateError> {
    execute_official_installer_with_assignment_callback(
        installer_path,
        install_prefix,
        modify_path,
        target_version,
        astral_mirror_url,
        installer_config_path,
        || Ok(()),
    )
    .await
}

async fn execute_official_installer_with_assignment_callback<F>(
    installer_path: &Path,
    install_prefix: &Path,
    modify_path: bool,
    target_version: &Pep440Version,
    astral_mirror_url: Option<&str>,
    installer_config_path: Option<&Path>,
    on_assigned: F,
) -> Result<(), AxoupdateError>
where
    F: FnOnce() -> Result<(), AxoupdateError>,
{'''

if text.count(signature) != 1:
    raise SystemExit(f"expected one installer signature, found {text.count(signature)}")
text = text.replace(signature, replacement, 1)

output_line = "    let output = command.output().await?;"
output_replacement = '''    #[cfg(windows)]
    let output = {
        let mut child = command.spawn()?;
        let raw_handle = child.raw_handle().ok_or_else(|| {
            std::io::Error::other("installer exited before Job Object assignment")
        })?;
        let job = uv_windows::Job::new_strict_tree()
            .map_err(|error| std::io::Error::other(error.to_string()))?;
        // SAFETY: Tokio returned the raw handle for this still-live child.
        unsafe { job.assign_raw_process_handle(raw_handle) }
            .map_err(|error| std::io::Error::other(error.to_string()))?;
        on_assigned()?;
        child.wait_with_output().await?
    };
    #[cfg(not(windows))]
    let output = {
        on_assigned()?;
        command.output().await?
    };'''

if text.count(output_line) != 1:
    raise SystemExit(f"expected one command.output line, found {text.count(output_line)}")
text = text.replace(output_line, output_replacement, 1)

test = r'''

    #[cfg(windows)]
    #[tokio::test]
    async fn fieldwork_strict_installer_job_terminates_spawned_descendant_on_cancellation() {
        let temp_dir = TempDir::new().unwrap();
        let installer_path = temp_dir.path().join("installer.ps1");
        let child_script = temp_dir.path().join("child.ps1");
        let install_prefix = temp_dir.path().join("install-prefix");
        let release_path = temp_dir.path().join("release-parent");
        let assigned_path = temp_dir.path().join("job-assigned");
        let parent_ready_path = temp_dir.path().join("parent-ready");
        let child_started_path = temp_dir.path().join("child-started");
        let child_survived_path = temp_dir.path().join("child-survived");

        fn ps_literal(path: &Path) -> String {
            format!("'{}'", path.display().to_string().replace('\'', "''"))
        }

        fs_err::write(
            &child_script,
            format!(
                "[IO.File]::WriteAllText({}, 'started')\nStart-Sleep -Seconds 4\n[IO.File]::WriteAllText({}, 'survived')\n",
                ps_literal(&child_started_path),
                ps_literal(&child_survived_path),
            ),
        )
        .unwrap();
        fs_err::write(
            &installer_path,
            format!(
                "[IO.File]::WriteAllText({}, 'ready')\nwhile (-not (Test-Path -LiteralPath {})) {{ Start-Sleep -Milliseconds 10 }}\nStart-Process -FilePath 'powershell' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', {}) -WindowStyle Hidden\nwhile ($true) {{ Start-Sleep -Milliseconds 100 }}\n",
                ps_literal(&parent_ready_path),
                ps_literal(&release_path),
                ps_literal(&child_script),
            ),
        )
        .unwrap();

        let task_installer = installer_path.clone();
        let task_prefix = install_prefix.clone();
        let task_release = release_path.clone();
        let task_assigned = assigned_path.clone();
        let task = tokio::spawn(async move {
            execute_official_installer_with_assignment_callback(
                &task_installer,
                &task_prefix,
                true,
                &Pep440Version::new([1, 2, 3]),
                None,
                None,
                move || {
                    fs_err::write(&task_assigned, "assigned")?;
                    fs_err::write(&task_release, "release")?;
                    Ok(())
                },
            )
            .await
        });

        for _ in 0..600 {
            if assigned_path.exists() && parent_ready_path.exists() && child_started_path.exists() {
                break;
            }
            if task.is_finished() {
                panic!("installer task finished before descendant started");
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        assert!(assigned_path.exists(), "strict Job assignment callback should run");
        assert!(parent_ready_path.exists(), "PowerShell parent should start");
        assert!(
            child_started_path.exists(),
            "PowerShell descendant should start after assignment"
        );

        task.abort();
        let join = task.await.expect_err("updater task should be cancelled");
        assert!(join.is_cancelled(), "task should report cancellation");

        tokio::time::sleep(Duration::from_secs(6)).await;
        assert!(
            !child_survived_path.exists(),
            "strict installer Job should terminate inherited descendant on cancellation"
        );
    }
'''

index = text.rfind("\n}")
if index < 0:
    raise SystemExit("test module close not found")
path.write_text(text[:index] + test + text[index:], encoding="utf-8")
