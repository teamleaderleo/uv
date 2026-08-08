#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/uv/src/commands/tool/upgrade.rs")
text = path.read_text()

replacements = [
    (
        '''    // Determine whether we applied any upgrades.\n    let mut did_upgrade_environment = vec![];\n\n    // Constraints that caused upgrades to be skipped or altered.\n''',
        '''    // Determine whether we applied any upgrades.\n    let mut did_upgrade_environment = vec![];\n\n    // Determine whether we repaired public entrypoints left incomplete by an earlier upgrade.\n    let mut did_repair_entrypoints = vec![];\n\n    // Constraints that caused upgrades to be skipped or altered.\n''',
    ),
    (
        '''                if let Some(constraint) = report.constraint.clone() {\n                    collected_constraints.push((name.clone(), constraint));\n                }\n''',
        '''                if report.repaired_entrypoints {\n                    did_repair_entrypoints.push(name);\n                }\n\n                if let Some(constraint) = report.constraint.clone() {\n                    collected_constraints.push((name.clone(), constraint));\n                }\n''',
    ),
    (
        '''    if did_upgrade_tool.is_empty() && did_upgrade_environment.is_empty() {\n        writeln!(printer.stderr(), "Nothing to upgrade")?;\n    }\n\n    if let Some(python_request) = python_request {\n''',
        '''    if did_upgrade_tool.is_empty()\n        && did_upgrade_environment.is_empty()\n        && did_repair_entrypoints.is_empty()\n    {\n        writeln!(printer.stderr(), "Nothing to upgrade")?;\n    }\n\n    if !did_repair_entrypoints.is_empty() {\n        let tools = did_repair_entrypoints\n            .iter()\n            .map(|name| format!("`{}`", name.cyan()))\n            .collect::<Vec<_>>();\n        writeln!(\n            printer.stderr(),\n            "Repaired tool entrypoints for {}",\n            conjunction(tools),\n        )?;\n    }\n\n    if let Some(python_request) = python_request {\n''',
    ),
    (
        '''struct UpgradeReport {\n    outcome: UpgradeOutcome,\n    constraint: Option<UpgradeConstraint>,\n}\n''',
        '''struct UpgradeReport {\n    outcome: UpgradeOutcome,\n    constraint: Option<UpgradeConstraint>,\n    repaired_entrypoints: bool,\n}\n''',
    ),
]
for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"unexpected replacement count for anchor {old[:80]!r}: {text.count(old)}")
    text = text.replace(old, new)

old_finalize = '''    if matches!(\n        outcome,\n        UpgradeOutcome::UpgradeEnvironment | UpgradeOutcome::UpgradeTool\n    ) {\n        // At this point, we updated the existing environment, so we should remove any of its\n        // existing executables.\n        remove_entrypoints(&existing_tool_receipt);\n\n        let entrypoints: Vec<_> = existing_tool_receipt\n            .entrypoints()\n            .iter()\n            .filter_map(|entry| PackageName::from_str(entry.from.as_ref()?).ok())\n            .collect();\n\n        // If we modified the target tool, reinstall the entrypoints.\n        finalize_tool_install(\n            &environment,\n            name,\n            &entrypoints,\n            installed_tools,\n            &ToolOptions::from(options),\n            true,\n            existing_tool_receipt.python().to_owned(),\n            existing_tool_receipt.requirements().to_vec(),\n            existing_tool_receipt.constraints().to_vec(),\n            existing_tool_receipt.overrides().to_vec(),\n            existing_tool_receipt.excludes().to_vec(),\n            existing_tool_receipt.build_constraints().to_vec(),\n            tool_lock.as_ref(),\n            printer,\n        )?;\n    } else if tool_locks {\n'''
new_finalize = '''    let entrypoint_recovery = tool_dir.join(".uv-entrypoints-incomplete");\n    let recovery_pending = entrypoint_recovery.try_exists()?;\n    let changed_root = matches!(\n        outcome,\n        UpgradeOutcome::UpgradeEnvironment | UpgradeOutcome::UpgradeTool\n    );\n    let repaired_entrypoints = recovery_pending\n        && matches!(\n            outcome,\n            UpgradeOutcome::UpgradeDependencies | UpgradeOutcome::NoOp\n        );\n\n    if changed_root || repaired_entrypoints {\n        // Leave a tool-local marker between changing the root environment and publishing its public\n        // entrypoints. A later upgrade can retry that uv-owned publication step without using byte\n        // comparison, which could otherwise steal an entrypoint intentionally replaced by another\n        // tool through `--force`.\n        if !recovery_pending {\n            fs_err::write(&entrypoint_recovery, b"")?;\n        }\n\n        remove_entrypoints(&existing_tool_receipt);\n\n        let entrypoints: Vec<_> = existing_tool_receipt\n            .entrypoints()\n            .iter()\n            .filter_map(|entry| PackageName::from_str(entry.from.as_ref()?).ok())\n            .collect();\n\n        finalize_tool_install(\n            &environment,\n            name,\n            &entrypoints,\n            installed_tools,\n            &ToolOptions::from(options),\n            true,\n            existing_tool_receipt.python().to_owned(),\n            existing_tool_receipt.requirements().to_vec(),\n            existing_tool_receipt.constraints().to_vec(),\n            existing_tool_receipt.overrides().to_vec(),\n            existing_tool_receipt.excludes().to_vec(),\n            existing_tool_receipt.build_constraints().to_vec(),\n            tool_lock.as_ref(),\n            if repaired_entrypoints {\n                Printer::Silent\n            } else {\n                printer\n            },\n        )?;\n\n        if let Err(err) = fs_err::remove_file(&entrypoint_recovery)\n            && err.kind() != std::io::ErrorKind::NotFound\n        {\n            return Err(err.into());\n        }\n    } else if tool_locks {\n'''
if text.count(old_finalize) != 1:
    raise SystemExit(f"unexpected finalization block count: {text.count(old_finalize)}")
text = text.replace(old_finalize, new_finalize)

old_report = '''    Ok(UpgradeReport {\n        outcome,\n        constraint,\n    })\n'''
new_report = '''    Ok(UpgradeReport {\n        outcome,\n        constraint,\n        repaired_entrypoints,\n    })\n'''
if text.count(old_report) != 1:
    raise SystemExit(f"unexpected report block count: {text.count(old_report)}")
text = text.replace(old_report, new_report)

path.write_text(text)
