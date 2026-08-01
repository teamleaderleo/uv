#[cfg(windows)]
fn main() {
    use std::path::PathBuf;

    let missing_replacement = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .expect("missing replacement path argument");
    assert!(
        !missing_replacement.exists(),
        "the control requires a nonexistent replacement source"
    );

    match self_replace::self_replace(&missing_replacement) {
        Ok(()) => {
            eprintln!("unexpected self_replace success");
            std::process::exit(2);
        }
        Err(error) => {
            eprintln!("expected self_replace failure: {error}");
            std::process::exit(42);
        }
    }
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Windows-only Fieldwork execution control");
    std::process::exit(3);
}
