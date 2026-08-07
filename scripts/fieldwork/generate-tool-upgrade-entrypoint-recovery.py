#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/uv/src/commands/tool/upgrade.rs")
text = path.read_text()

replacements = [
    (
        '''    // Determine whether we applied any upgrades.\n    let mut did_upgrade_environment = vec![];\n\n    // Constraints that caused upgrades to be skipped or altered.\n''',
        '''    // Determine whether we applied any upgrades.\n    let mut did_upgrade_environment = vec![];\n\n    // Determine whether we repaired entrypoints left incomplete by a previous upgrade.\n    let mut did_repair_entrypoints = vec![];\n\n    // Constraints that caused upgrades to be skipped or altered.\n''',
    ),
    (
        '''                    UpgradeOutcome::NoOp => {\n                        debug!("Upgrading `{name}` was a no-op");\n                    }\n''',
        '''                    UpgradeOutcome::RepairEntrypoints => {\n                        did_repair_entrypoints.push(name);\n                    }\n                    UpgradeOutcome::NoOp => {\n                        debug!("Upgrading `{name}` was a no-op");\n                    }\n''',
    ),
    (
        '''    if did_upgrade_tool.is_empty() && did_upgrade_environment.is_empty() {\n        writeln!(printer.stderr(), "Nothing to upgrade")?;\n    }\n\n    if let Some(python_request) = python_request {\n''',
        '''    if did_upgrade_tool.is_empty()\n        && did_upgrade_environment.is_empty()\n        && did_repair_entrypoints.is_empty()\n    {\n        writeln!(printer.stderr(), "Nothing to upgrade")?;\n    }\n\n    if !did_repair_entrypoints.is_empty() {\n        let tools = did_repair_entrypoints\n            .iter()\n            .map(|name| format!("`{}`", name.cyan()))\n            .collect::<Vec<_>>();\n        writeln!(\n            printer.stderr(),\n            "Repaired tool entrypoints for {}",\n            conjunction(tools),\n        )?;\n    }\n\n    if let Some(python_request) = python_request {\n''',
    ),
    (
        '''    /// The tool was already up-to-date.\n    NoOp,\n''',
        '''    /// Public entrypoints were repaired after an earlier publication failure.\n    RepairEntrypoints,\n    /// The tool was already up-to-date.\n    NoOp,\n''',
    ),
    (
        '''    let (environment, outcome, tool_lock) = if tool_locks {\n''',
        '''    let (environment, mut outcome, tool_lock) = if tool_locks {\n''',
    ),
]

for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"unexpected replacement count for anchor: {old[:80]!r}: {text.count(old)}")
    text = text.replace(old, new)

old_finalize = '''    if matches!(\n        outcome,\n        UpgradeOutcome::UpgradeEnvironment | UpgradeOutcome::UpgradeTool\n    ) {\n        // At this point, we updated the existing environment, so we should remove any of its\n        // existing executables.\n        remove_entrypoints(&existing_tool_receipt);\n\n        let entrypoints: Vec<_> = existing_tool_receipt\n            .entrypoints()\n            .iter()\n            .filter_map(|entry| PackageName::from_str(entry.from.as_ref()?).ok())\n            .collect();\n\n        // If we modified the target tool, reinstall the entrypoints.\n        finalize_tool_install(\n            &environment,\n            name,\n            &entrypoints,\n            installed_tools,\n            &ToolOptions::from(options),\n            true,\n            existing_tool_receipt.python().to_owned(),\n            existing_tool_receipt.requirements().to_vec(),\n            existing_tool_receipt.constraints().to_vec(),\n            existing_tool_receipt.overrides().to_vec(),\n            existing_tool_receipt.excludes().to_vec(),\n            existing_tool_receipt.build_constraints().to_vec(),\n            tool_lock.as_ref(),\n            printer,\n        )?;\n    } else if tool_locks {\n'''
new_finalize = '''    let entrypoint_recovery = tool_dir.join(".uv-entrypoints-incomplete");\n    let repair_entrypoints =\n        outcome == UpgradeOutcome::NoOp && entrypoint_recovery.try_exists()?;\n\n    if matches!(\n        outcome,\n        UpgradeOutcome::UpgradeEnvironment | UpgradeOutcome::UpgradeTool\n    ) || repair_entrypoints\n    {\n        // Once the environment has changed, leave a recovery marker until its public entrypoints\n        // and receipt are successfully finalized. A later no-op upgrade can then retry only this\n        // uv-owned publication step without rewriting healthy entrypoints.\n        if !repair_entrypoints {\n            fs_err::write(&entrypoint_recovery, b"")?;\n        }\n\n        // At this point, we updated the existing environment, so we should remove any of its\n        // existing executables.\n        remove_entrypoints(&existing_tool_receipt);\n\n        let entrypoints: Vec<_> = existing_tool_receipt\n            .entrypoints()\n            .iter()\n            .filter_map(|entry| PackageName::from_str(entry.from.as_ref()?).ok())\n            .collect();\n\n        // If we modified the target tool, reinstall the entrypoints. Suppress the generic\n        // installation message when this is a recovery-only retry; the caller reports the repair.\n        finalize_tool_install(\n            &environment,\n            name,\n            &entrypoints,\n            installed_tools,\n            &ToolOptions::from(options),\n            true,\n            existing_tool_receipt.python().to_owned(),\n            existing_tool_receipt.requirements().to_vec(),\n            existing_tool_receipt.constraints().to_vec(),\n            existing_tool_receipt.overrides().to_vec(),\n            existing_tool_receipt.excludes().to_vec(),\n            existing_tool_receipt.build_constraints().to_vec(),\n            tool_lock.as_ref(),\n            if repair_entrypoints {\n                Printer::Silent\n            } else {\n                printer\n            },\n        )?;\n        fs_err::remove_file(&entrypoint_recovery)?;\n\n        if repair_entrypoints {\n            outcome = UpgradeOutcome::RepairEntrypoints;\n        }\n    } else if tool_locks {\n'''
if text.count(old_finalize) != 1:
    raise SystemExit(f"unexpected finalization block count: {text.count(old_finalize)}")
text = text.replace(old_finalize, new_finalize)

old_constraint = '''        UpgradeOutcome::UpgradeDependencies | UpgradeOutcome::NoOp => {\n            pinned_requirement_version(&existing_tool_receipt, name)\n                .map(|version| UpgradeConstraint::PinnedVersion { version })\n        }\n        UpgradeOutcome::UpgradeTool | UpgradeOutcome::UpgradeEnvironment => None,\n'''
new_constraint = '''        UpgradeOutcome::UpgradeDependencies\n        | UpgradeOutcome::RepairEntrypoints\n        | UpgradeOutcome::NoOp => pinned_requirement_version(&existing_tool_receipt, name)\n            .map(|version| UpgradeConstraint::PinnedVersion { version }),\n        UpgradeOutcome::UpgradeTool | UpgradeOutcome::UpgradeEnvironment => None,\n'''
if text.count(old_constraint) != 1:
    raise SystemExit(f"unexpected constraint block count: {text.count(old_constraint)}")
text = text.replace(old_constraint, new_constraint)

path.write_text(text)
