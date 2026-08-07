# Fieldwork: Windows path-case duplicates in `uv python list`

Observed upstream report: https://redirect.github.com/astral-sh/uv/issues/13505  
Related completed report: https://redirect.github.com/astral-sh/uv/issues/9979  
Related historical change: https://redirect.github.com/astral-sh/uv/pull/12628  
Inspected fork base: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`  
External contact: **not authorized and not performed**

## Current classification

`SOURCE/HISTORY MAPPED — PATH-ONLY REPRODUCER REJECTED — PATH+REGISTRY DISCRIMINATOR SELECTED — CANDIDATE UNEXECUTED`

The historical fix intentionally changed `uv python list` to display the queried executable path (`Interpreter::real_executable`) rather than Python's resolved `sys.executable`. That preserves useful information about shims and search-path entries.

The final listing command removes duplicate queried paths with an `FxHashSet<PathBuf>`. Rust path equality is lexical and case-sensitive, so the final-stage code can retain Windows case variants.

## Executed Windows result

Read-only carrier run `31047448111`, job `92446355170`, used packet `bef3a851268867f6c85cab49aa998471cc7af873` on Windows Server 2022.

The carrier:

- checked out the immutable baseline and candidate source;
- applied the UTF-16 case-variant PATH control and candidate transformer cleanly;
- compiled the baseline successfully;
- ran exactly one focused `python_list_duplicate_path_entries` test;
- observed the baseline test **pass**, listing each Python once;
- skipped the candidate stage because the required baseline failure was absent.

Artifact `8948402487`, SHA-256 `a136314c4f7d4b21c7d29fdd105de187fb6faccedfd1d01815485964ea37aabc`, retains the baseline transcript.

This is not evidence that issue #13505 is fixed and not evidence for the candidate. It establishes only that case-varied copies of the same directories in `UV_PYTHON_SEARCH_PATH` do not reproduce the report on the tested head.

## Why the PATH-only control passes

Source review now identifies the early dedup layer precisely.

`python_executables_from_search_path()` splits the configured search path into directories, opens each directory with `same_file::Handle`, and skips directory identities already seen. This is file-identity dedup before any interpreter query. Therefore adding the same directory again with only a different Windows spelling is intentionally collapsed before `python list` ever receives two installations.

That behavior does **not** generalize across discovery sources.

For `PythonPreference::OnlySystem`, installed discovery is explicitly:

1. search-path executables;
2. Windows registry / Microsoft Store executables.

`find_all_python_installations()` then simply collects every successful `PythonInstallation`; it performs no cross-source path deduplication.

Each `Interpreter::query(executable, ...)` stores the supplied executable path directly as `real_executable`. A registry `ExecutablePath` whose spelling differs only by Windows case from a search-path spelling therefore survives interpreter probing as a distinct queried path even though both paths address the same file.

Finally, `uv python list` inserts those `real_executable` paths into `FxHashSet<PathBuf>`. That is the first cross-source dedup at the listing boundary, and it is case-sensitive.

This source chain makes PATH + PEP 514 registry discovery the preferred next reproducer.

## Preferred next discriminator

Use the repository's existing opt-in Windows-registry test model. The `uv` crate already defines `test-windows-registry` specifically for tests that mutate global registry state, and Windows CI enables that feature.

A focused Windows control should:

1. create a one-version test context, preferably CPython 3.12;
2. identify the exact executable spelling produced through `UV_PYTHON_SEARCH_PATH`;
3. create a temporary HKCU PEP 514 company/tag under `Software\\Python` with:
   - `SysVersion = 3.12`;
   - `InstallPath\\ExecutablePath` equal to the **same executable** but with a UTF-16 ASCII case toggle in an ordinary path component;
4. prove the case-varied path exists and differs byte/code-unit-wise from the PATH spelling;
5. run `uv python list 3.12 --only-installed` with registry discovery enabled and the controlled search path;
6. require the baseline to expose both case spellings of the same queried executable, or otherwise record why one source was filtered before the final list;
7. require the candidate to emit only one of those case-equivalent paths;
8. remove the temporary HKCU company key in cleanup even on assertion failure where practical;
9. keep a negative control showing genuinely distinct shim/search-path locations are not collapsed merely because they resolve to the same Python installation.

The registry key must be uniquely named per test process to avoid collisions with other opt-in registry tests. No HKLM mutation is needed.

If the PATH + registry baseline still does not duplicate, the transcript must identify which source disappeared. Only then should the investigation fall back to a test seam immediately before final inclusion.

## Retained semantic boundary

Do **not** replace lexical comparison with file-identity deduplication. Distinct symlink, shim, registry, and search-path entries can be meaningful provenance. A repair should collapse only queried paths equal under Windows ordinal case-insensitive semantics while preserving genuinely distinct discovery entries.

The retained design sketch uses `CompareStringOrdinal` over UTF-16 through `uv-windows`, with unchanged non-Windows behavior. It remains **unexecuted** because the earlier end-to-end baseline control was invalid.

## Execution gate

No new Windows carrier should run until the PATH + registry fixture exists in source form and static review confirms:

- registry cleanup ownership;
- no dependence on host-installed registry Pythons for the asserted result;
- exact baseline/candidate discriminator;
- a provenance-preserving negative control;
- source/test diff fence;
- no source publication by the carrier.

No product source has been materialized. This packet is not an upstream contribution claim.
