#[cfg(windows)]
use std::env;
#[cfg(windows)]
use std::path::PathBuf;
use std::process::ExitCode;

#[cfg(windows)]
fn main() -> ExitCode {
    let mut args = env::args_os();
    let _program = args.next();

    let Some(parent_process_id) = args.next() else {
        return usage("missing parent process id");
    };
    let Some(canonical) = args.next() else {
        return usage("missing canonical executable path");
    };
    let Some(replacement) = args.next() else {
        return usage("missing replacement path");
    };

    let mut fail_after_backup = false;
    let mut ready_path = None;
    while let Some(argument) = args.next() {
        if argument == "--fail-after-backup" {
            if fail_after_backup {
                return usage("duplicate --fail-after-backup");
            }
            fail_after_backup = true;
        } else if argument == "--ready-file" {
            if ready_path.is_some() {
                return usage("duplicate --ready-file");
            }
            let Some(path) = args.next() else {
                return usage("missing path after --ready-file");
            };
            ready_path = Some(PathBuf::from(path));
        } else {
            return usage(&format!(
                "unknown argument `{}`",
                argument.to_string_lossy()
            ));
        }
    }

    let process_id = match parent_process_id.to_string_lossy().parse::<u32>() {
        Ok(process_id) => process_id,
        Err(error) => return usage(&format!("invalid parent process id: {error}")),
    };

    let options = uv_windows::UpdateFinalizeOptions {
        fail_after_backup,
        ready_path,
    };
    match uv_windows::finalize_update_after_process_exit(
        process_id,
        &PathBuf::from(canonical),
        &PathBuf::from(replacement),
        options,
    ) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("deferred update finalizer failed: {error}");
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
        "{message}\nusage: fieldwork_deferred_update_finalizer <parent-pid> <canonical> <replacement> [--ready-file <path>] [--fail-after-backup]"
    );
    ExitCode::from(2)
}
