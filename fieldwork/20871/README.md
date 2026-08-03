# Fieldwork: uvx project-dependency report — negative result

Upstream issue: https://github.com/astral-sh/uv/issues/20871  
Inspected upstream source: `79bbface771210df216b738e9bdc7df95e5a9e6b`  
Fork branch base was advanced to that exact upstream commit.  
External contact: **not authorized and not performed**

## In simple words

The reported defect was not in uv. The reporter reduced the problem and found that their own tool invoked `uv run` internally, so its behavior legitimately depended on the launch directory and discovered project.

Our source review independently found that `uvx` itself selects a system interpreter and an installed-tool or cached tool environment; it does not reuse the surrounding project's `.venv`. The pending ambient-import-path probe is therefore no longer a prerequisite for this report and has been retired.

## Upstream resolution

The issue was closed as completed on 2026-08-02. The reporter stated that uv was not the culprit and identified the internal `uv run` invocation in their tool as the cause. The maintainer acknowledged the follow-up.

## Retained source findings

- tool interpreter discovery uses `EnvironmentPreference::OnlySystem`;
- non-isolated reuse is limited to uv's installed-tools store, not the current project `.venv`;
- fresh execution uses `CachedEnvironment::from_spec`;
- the launched command receives a `PATH` beginning with the tool environment's scripts directory;
- ambient environment variables remain inherited, but that was not the cause established by the reporter;
- uv's global `--isolated` option is documented as disabling configuration discovery and is deprecated in favor of `--no-config`; it is not a promise to scrub Python import variables.

## Artifacts

The local path-package probe remains under `fieldwork/20871/` as a reusable diagnostic for ambient `PYTHONPATH` questions. It is retained but not presented as executed evidence for this issue.

## Disposition

**Negative result — stop.** No production source change is justified, no upstream proposal should be prepared, and this fork draft should remain closed unless a new clean reproduction shows a distinct uv defect.

Evidence state: `source-reviewed`; `public-record verified`; probe `prepared but not executed`; no upstream contact.
