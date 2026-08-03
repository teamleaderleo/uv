# Fieldwork: uvx and ambient Python import paths

Upstream issue: https://github.com/astral-sh/uv/issues/20871  
Inspected upstream source: `79bbface771210df216b738e9bdc7df95e5a9e6b`  
Fork branch base was advanced to that exact upstream commit.  
External contact: **not authorized and not performed**

## In simple words

Current `uvx` code does not discover or reuse the surrounding project's virtual environment. It selects a system interpreter, resolves the tool into an installed-tool or cached tool environment, and prepends that environment's scripts directory to `PATH`.

The child process otherwise inherits the ambient environment. In particular, `PYTHONPATH` is not removed and Python isolation variables are not added. That makes an externally injected import path the leading explanation for a tool importing a project copy of a dependency. This matches the maintainer's unanswered question about `PYTHONPATH` and the executable in use.

## What is known

- tool interpreter discovery uses `EnvironmentPreference::OnlySystem`;
- non-isolated reuse is limited to uv's installed-tools store, not the current project `.venv`;
- fresh execution uses `CachedEnvironment::from_spec`;
- `--isolated` disables installed-tool reuse but does not sanitize the child environment;
- the child inherits the current working directory and all environment variables except the explicitly replaced `PATH` and any values from `--env-file`.

## Discriminating matrix

Run `probe.sh` and record all four rows:

1. no ambient `PYTHONPATH`;
2. `PYTHONPATH` points at a conflicting module;
3. same conflict with `uvx --isolated`;
4. same conflict after manually unsetting `PYTHONPATH` and setting `PYTHONNOUSERSITE=1`.

The probe uses only local path packages and does not need PyPI.

## Decision gate

- If contamination occurs only with `PYTHONPATH`, classify the report as ambient-environment behavior. A product change would require an explicit policy decision about whether `uvx` should sanitize Python variables by default or only under `--isolated`.
- If contamination occurs with `PYTHONPATH` absent, capture `sys.executable`, `sys.prefix`, `sys.path`, entry-point shebang, cache key, and current directory before touching production code.
- Do not clear `PYTHONPATH` unconditionally without checking documented uv behavior and workflows that intentionally use it.

## Candidate policy, not yet selected

The least surprising bounded change would be to make `--isolated` remove `PYTHONPATH` and `PYTHONHOME`, set `PYTHONNOUSERSITE=1`, and document the behavior. Extending that to default `uvx` is a separate compatibility choice.

## Evidence state

`source-reviewed`; `reproducer-prepared`; not executed in this environment. No production patch is promoted until the matrix distinguishes ambient injection from an actual environment-selection defect.