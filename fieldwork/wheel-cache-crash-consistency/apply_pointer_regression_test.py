#!/usr/bin/env python3
"""Add a repository-native regression for missing local wheel archives."""

from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv/tests/pip/pip_sync.rs"
text = path.read_text(encoding="utf-8")

old_import = "use wiremock::{Mock, MockServer, ResponseTemplate};\n"
new_import = old_import + "use walkdir::WalkDir;\n"
if text.count(old_import) != 1:
    raise SystemExit("pip_sync import insertion point mismatch")
text = text.replace(old_import, new_import)

marker = "/// Install a package into a virtual environment using hardlink semantics.\n"
test = r'''/// Re-extract a local wheel when its cached archive target has disappeared.
#[test]
fn recovers_missing_local_wheel_archive() -> Result<()> {
    fn find_archive(cache: &std::path::Path) -> PathBuf {
        let metadata = WalkDir::new(cache)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .find(|entry| {
                entry.file_type().is_file()
                    && entry.file_name() == "METADATA"
                    && entry
                        .path()
                        .parent()
                        .and_then(std::path::Path::file_name)
                        .is_some_and(|name| name == "tomli-2.0.1.dist-info")
            })
            .expect("cached tomli metadata");

        metadata
            .path()
            .ancestors()
            .find(|ancestor| {
                ancestor
                    .parent()
                    .and_then(std::path::Path::file_name)
                    .is_some_and(|name| name.to_string_lossy().starts_with("archive-v"))
            })
            .expect("archive root")
            .to_path_buf()
    }

    let context = uv_test::test_context!("3.12");
    let wheel = context.temp_dir.child("tomli-2.0.1-py3-none-any.whl");
    download_to_disk(
        "https://files.pythonhosted.org/packages/97/75/10a9ebee3fd790d20926a90a2547f0bf78f371b2f13aa822c759680ca7b9/tomli-2.0.1-py3-none-any.whl",
        &wheel,
    );
    let wheel_before = fs::read(wheel.path())?;

    let requirements = context.temp_dir.child("requirements.txt");
    requirements.write_str(&format!(
        "tomli @ {}",
        Url::from_file_path(wheel.path()).unwrap()
    ))?;

    context
        .pip_sync()
        .arg("requirements.txt")
        .arg("--strict")
        .assert()
        .success();
    context.assert_command("import tomli").success();

    let first_archive = find_archive(context.cache_dir.path());
    fs::remove_dir_all(&first_archive)?;
    assert!(!first_archive.exists());

    context.reset_venv();
    context
        .pip_sync()
        .arg("requirements.txt")
        .arg("--strict")
        .assert()
        .success();
    context.assert_command("import tomli").success();

    let second_archive = find_archive(context.cache_dir.path());
    assert_ne!(first_archive, second_archive);
    assert_eq!(wheel_before, fs::read(wheel.path())?);

    Ok(())
}

'''
if text.count(marker) != 1:
    raise SystemExit("pip_sync regression insertion point mismatch")
text = text.replace(marker, test + marker)
path.write_text(text, encoding="utf-8")
print(path)
