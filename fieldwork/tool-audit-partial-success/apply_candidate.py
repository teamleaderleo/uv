#!/usr/bin/env python3
"""Apply a bounded tool-audit completeness repair and focused controls."""

from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(path: Path, old: str, new: str, *, name: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{name} mismatch in {path}: expected {count}, found {actual}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def function_section(text: str, function: str) -> tuple[int, int, str]:
    start = text.index(f"fn {function}")
    next_test = text.find("\n#[", start + 1)
    end = len(text) if next_test == -1 else next_test
    return start, end, text[start:end]


audit = root / "crates/uv/src/commands/tool/audit.rs"
replace(
    audit,
    """    let mut audits = Vec::new();
    let mut matched_ignores = FxHashSet::default();
""",
    """    let mut audits = Vec::new();
    let mut matched_ignores = FxHashSet::default();
    let mut skipped_tools = false;
""",
    name="skipped-tools state",
)

for name, warning in [
    (
        "malformed receipt",
        """                warn_user!(
                    "Ignoring malformed tool `{name}` (run `uv tool uninstall {name}` to remove)"
                );
                continue;
""",
    ),
    (
        "missing lockfile",
        """                warn_user!(
                    "Skipping tool `{name}` because it does not have a lockfile; reinstall it with `--preview-features tool-install-locks` to audit it"
                );
                continue;
""",
    ),
    (
        "unreadable lockfile",
        """                warn_user!(
                    "Skipping tool `{name}` because its lockfile at `{}` could not be read: {error}",
                    lock_path.user_display()
                );
                continue;
""",
    ),
    (
        "unsupported lockfile",
        """                warn_user!(
                    "Skipping tool `{name}` because its lockfile at `{}` uses an unsupported schema version (v{version}, but only v{supported} is supported)",
                    lock_path.user_display()
                );
                continue;
""",
    ),
    (
        "invalid lockfile",
        """                warn_user!(
                    "Skipping tool `{name}` because its lockfile at `{}` is invalid: {error}",
                    lock_path.user_display()
                );
                continue;
""",
    ),
]:
    replace(
        audit,
        warning,
        warning.replace(
            "                continue;",
            "                skipped_tools = true;\n                continue;",
        ),
        name=name,
    )

replace(
    audit,
    """    if audits.is_empty() && matches!(output_format, AuditOutputFormat::Text) {
        writeln!(printer.stderr(), "No auditable tools installed")?;
        return Ok(ExitStatus::Success);
    }

    render_audits(&audits, output_format, printer)
""",
    """    if audits.is_empty() && matches!(output_format, AuditOutputFormat::Text) {
        writeln!(printer.stderr(), "No auditable tools installed")?;
        return Ok(if skipped_tools {
            ExitStatus::Failure
        } else {
            ExitStatus::Success
        });
    }

    let status = render_audits(&audits, output_format, printer)?;
    Ok(if skipped_tools {
        ExitStatus::Failure
    } else {
        status
    })
""",
    name="partial-audit exit status",
)

tests = root / "crates/uv/tests/tool/tool_audit.rs"
text = tests.read_text(encoding="utf-8")

# These all-tools tests have one aggregate success snapshot each. Explicit named-tool
# failure snapshots in the same functions are intentionally left unchanged.
for function in [
    "tool_audit_missing_lockfile",
    "tool_audit_invalid_receipt",
    "tool_audit_invalid_lockfile",
    "tool_audit_unsupported_lockfile_version",
    "tool_audit_mixed_lockfiles",
]:
    start, end, section = function_section(text, function)
    if section.count("exit_code: 0 (success)") != 1:
        raise SystemExit(f"{function} expected one aggregate success snapshot")
    section = section.replace("exit_code: 0 (success)", "exit_code: 2 (failure)", 1)
    text = text[:start] + section + text[end:]

# The SARIF no-auditable test has two snapshots: a truly empty inventory should
# remain success; only the second snapshot (installed but skipped tool) becomes failure.
start, end, section = function_section(text, "tool_audit_sarif_no_auditable_tools")
if section.count("exit_code: 0 (success)") != 2:
    raise SystemExit("SARIF no-auditable test expected two success snapshots")
last = section.rfind("exit_code: 0 (success)")
section = section[:last] + "exit_code: 2 (failure)" + section[last + len("exit_code: 0 (success)") :]
text = text[:start] + section + text[end:]

# JSON should keep rendering the valid empty schema while signaling incomplete coverage.
marker = """#[tokio::test]
async fn tool_audit_json_preview_warning() {
"""
json_test = r'''#[test]
fn tool_audit_json_no_auditable_tools_after_skip() {
    let context = uv_test::test_context!("3.12");
    let tool_dir = context.temp_dir.child("tools");
    install_tool(&context, "simple-launcher", false);

    uv_snapshot!(context.filters(), context.tool_audit()
        .arg("--all")
        .arg("--output-format")
        .arg("json")
        .env(EnvVars::UV_PREVIEW_FEATURES, "audit,tool-install-locks,json-output")
        .env(EnvVars::UV_TOOL_DIR, tool_dir.as_os_str()), @r#"
    exit_code: 2 (failure)
    ----- stdout -----
    {
      "schema": {
        "version": "preview"
      },
      "tools": []
    }

    ----- stderr -----
    warning: Skipping tool `simple-launcher` because it does not have a lockfile; reinstall it with `--preview-features tool-install-locks` to audit it
    "#);
}

'''
if text.count(marker) != 1:
    raise SystemExit("JSON skipped-tool insertion point mismatch")
text = text.replace(marker, json_test + marker)

tests.write_text(text, encoding="utf-8")
print(root)
