use std::env;
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
    let fail_after_backup = args.next().is_some_and(|arg| arg == "--fail-after-backup");
    if args.next().is_some() {
        return usage("too many arguments");
    }

    let process_id = match parent_process_id.to_string_lossy().parse::<u32>() {
        Ok(process_id) => process_id,
        Err(error) => return usage(&format!("invalid parent process id: {error}")),
    };

    let options = uv_windows::UpdateFinalizeOptions { fail_after_backup };
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
        "{message}\nusage: fieldwork_deferred_update_finalizer <parent-pid> <canonical> <replacement> [--fail-after-backup]"
    );
    ExitCode::from(2)
}
