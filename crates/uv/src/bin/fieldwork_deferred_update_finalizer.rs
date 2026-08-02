use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

#[cfg(windows)]
fn main() -> ExitCode {
    let mut args = env::args_os();
    let _program = args.next();

    let Some(first) = args.next() else {
        return usage("missing command or parent process id");
    };

    if first == "recover" {
        let Some(journal) = args.next() else {
            return usage("missing update journal path");
        };
        if args.next().is_some() {
            return usage("too many recovery arguments");
        }
        return finish_result(
            "update journal recovery",
            uv_windows::recover_update_from_journal(&PathBuf::from(journal)),
        );
    }

    let Some(canonical) = args.next() else {
        return usage("missing canonical executable path");
    };
    let Some(replacement) = args.next() else {
        return usage("missing replacement path");
    };
    let fail_after_backup = args.next().is_some_and(|arg| arg == "--fail-after-backup");
    if args.next().is_some() {
        return usage("too many finalize arguments");
    }

    let process_id = match first.to_string_lossy().parse::<u32>() {
        Ok(process_id) => process_id,
        Err(error) => return usage(&format!("invalid parent process id: {error}")),
    };

    finish_result(
        "deferred update finalizer",
        uv_windows::finalize_update_after_process_exit(
            process_id,
            &PathBuf::from(canonical),
            &PathBuf::from(replacement),
            uv_windows::UpdateFinalizeOptions { fail_after_backup },
        ),
    )
}

#[cfg(windows)]
fn finish_result(operation: &str, result: std::io::Result<()>) -> ExitCode {
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{operation} failed: {error}");
            ExitCode::from(42)
        }
    }
}

#[cfg(not(windows))]
fn main() -> ExitCode {
    eprintln!("the deferred update finalizer prototype is Windows-only");
    ExitCode::from(2)
}

fn usage(message: &str) -> ExitCode {
    eprintln!(
        "{message}\nusage:\n  fieldwork_deferred_update_finalizer <parent-pid> <canonical> <replacement> [--fail-after-backup]\n  fieldwork_deferred_update_finalizer recover <journal>"
    );
    ExitCode::from(2)
}
