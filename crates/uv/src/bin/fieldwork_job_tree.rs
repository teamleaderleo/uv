#[cfg(windows)]
use std::env;
#[cfg(windows)]
use std::fs;
#[cfg(windows)]
use std::path::{Path, PathBuf};
#[cfg(windows)]
use std::process::{Command, Stdio};
use std::process::ExitCode;
#[cfg(windows)]
use std::thread;
#[cfg(windows)]
use std::time::{Duration, Instant};

#[cfg(windows)]
fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("job-tree experiment failed: {error}");
            ExitCode::from(42)
        }
    }
}

#[cfg(windows)]
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args_os();
    let _program = args.next();
    let mode = args
        .next()
        .ok_or("missing mode: expected `silent` or `strict`")?;
    let root = PathBuf::from(args.next().ok_or("missing experiment directory")?);
    if args.next().is_some() {
        return Err("too many arguments".into());
    }

    let strict = match mode.to_string_lossy().as_ref() {
        "silent" => false,
        "strict" => true,
        other => return Err(format!("unknown mode `{other}`").into()),
    };

    fs::create_dir_all(&root)?;
    let release = root.join("release-parent");
    let parent_started = root.join("parent-started");
    let child_started = root.join("child-started");
    let child_survived = root.join("child-survived");
    let parent_script = root.join("parent.ps1");
    let child_script = root.join("child.ps1");

    fs::write(
        &child_script,
        format!(
            "[IO.File]::WriteAllText({}, 'started')\nStart-Sleep -Seconds 4\n[IO.File]::WriteAllText({}, 'survived')\n",
            ps_literal(&child_started),
            ps_literal(&child_survived),
        ),
    )?;
    fs::write(
        &parent_script,
        format!(
            "while (-not (Test-Path -LiteralPath {})) {{ Start-Sleep -Milliseconds 10 }}\n\
             Start-Process -FilePath 'powershell' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', {}) -WindowStyle Hidden\n\
             [IO.File]::WriteAllText({}, 'started')\n\
             while ($true) {{ Start-Sleep -Milliseconds 100 }}\n",
            ps_literal(&release),
            ps_literal(&child_script),
            ps_literal(&parent_started),
        ),
    )?;

    let mut parent = Command::new("powershell")
        .args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        ])
        .arg(&parent_script)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;

    let job = if strict {
        uv_windows::Job::new_strict_tree()?
    } else {
        uv_windows::Job::new()?
    };
    job.assign_child(&parent)?;

    // The parent cannot spawn its descendant until assignment is complete.
    fs::write(&release, b"release")?;
    wait_for_path(&parent_started, &mut parent, Duration::from_secs(30))?;
    wait_for_path(&child_started, &mut parent, Duration::from_secs(30))?;

    // Closing the Job handle is the cancellation event under test.
    drop(job);
    wait_for_exit(&mut parent, Duration::from_secs(15))?;

    // The child writes only if it survives the job close long enough to reach its delayed marker.
    thread::sleep(Duration::from_secs(6));
    let descendant_survived = child_survived.exists();
    match (strict, descendant_survived) {
        (false, true) | (true, false) => {}
        (false, false) => {
            return Err("silent-breakaway child unexpectedly remained supervised".into());
        }
        (true, true) => {
            return Err("strict job allowed descendant to survive job close".into());
        }
    }

    fs::write(
        root.join("result.txt"),
        format!(
            "mode={}\nparent_exited=true\ndescendant_survived={}\n",
            if strict { "strict" } else { "silent" },
            descendant_survived,
        ),
    )?;
    Ok(())
}

#[cfg(windows)]
fn wait_for_path(
    path: &Path,
    child: &mut std::process::Child,
    timeout: Duration,
) -> Result<(), Box<dyn std::error::Error>> {
    let deadline = Instant::now() + timeout;
    loop {
        if path.exists() {
            return Ok(());
        }
        if let Some(status) = child.try_wait()? {
            return Err(format!(
                "parent exited before marker `{}`: {status}",
                path.display()
            )
            .into());
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            return Err(format!("timed out waiting for marker `{}`", path.display()).into());
        }
        thread::sleep(Duration::from_millis(25));
    }
}

#[cfg(windows)]
fn wait_for_exit(
    child: &mut std::process::Child,
    timeout: Duration,
) -> Result<(), Box<dyn std::error::Error>> {
    let deadline = Instant::now() + timeout;
    loop {
        if child.try_wait()?.is_some() {
            return Ok(());
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            return Err("parent process survived Job handle close".into());
        }
        thread::sleep(Duration::from_millis(25));
    }
}

#[cfg(windows)]
fn ps_literal(path: &Path) -> String {
    format!("'{}'", path.display().to_string().replace('\'', "''"))
}

#[cfg(not(windows))]
fn main() -> ExitCode {
    eprintln!("the job-tree experiment is Windows-only");
    ExitCode::from(2)
}
