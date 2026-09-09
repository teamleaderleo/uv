# Fieldwork: Windows path-case duplicates in `uv python list`

Observed upstream report: https://redirect.github.com/astral-sh/uv/issues/13505  
Related completed report: https://redirect.github.com/astral-sh/uv/issues/9979  
Related historical change: https://redirect.github.com/astral-sh/uv/pull/12628  
Inspected fork base: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`  
External contact: **not authorized and not performed**

## Current classification

`SOURCE/HISTORY MAPPED — PATH-ONLY REPRODUCER REJECTED — PATH+REGISTRY FIXTURE PREPARED — CANDIDATE UNEXECUTED`

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

`python_executables_from_search_path()` splits the configured search path into directories, opens each directory with `same_file::Handle`, and skips directory identities already seen. This is file-identity dedup before any interpreter query. Therefore adding the same directory again with only a different Windows spelling is intentionally collapsed before `python list` ever receives two installations.

That behavior does **not** generalize across discovery sources.

For `PythonPreference::OnlySystem`, installed discovery is explicitly:

1. search-path executables;
2. Windows registry / Microsoft Store executables.

`find_all_python_installations()` then simply collects every successful `PythonInstallation`; it performs no cross-source path deduplication.

Each `Interpreter::query(executable, ...)` stores the supplied executable path directly as `real_executable`. A registry `ExecutablePath` whose spelling differs only by Windows case from a search-path spelling therefore survives interpreter probing as a distinct queried path even though both paths address the same file.

Finally, `uv python list` inserts those `real_executable` paths into `FxHashSet<PathBuf>`. That is the first cross-source dedup at the listing boundary, and it is case-sensitive.

## Prepared PATH + registry discriminator

`fieldwork/13505/apply_registry_candidate.py` is now the authoritative next execution packet.

Baseline mode (`--tests-only`) injects one opt-in Windows integration test into `python_list.rs`. Candidate mode injects the same test and applies only the retained ordinal-comparison source candidate from `apply_candidate.py`; it deliberately does **not** re-add the rejected duplicated-PATH control.

The fixture:

1. creates a one-version CPython 3.12 test context;
2. finds a real executable in the controlled `UV_PYTHON_SEARCH_PATH` using names that normal 3.12 discovery already searches;
3. produces a second spelling by toggling one ASCII UTF-16 code unit after the drive prefix;
4. requires that the case-varied spelling still resolves to the same test executable;
5. creates a unique per-process HKCU PEP 514 company/tag under `Software\\Python`;
6. writes `SysVersion = 3.12` and `InstallPath\\ExecutablePath` equal to the case-varied spelling;
7. runs `uv python list 3.12 --only-installed` with registry discovery explicitly enabled;
8. counts final output rows containing the deliberately selected executable path under ASCII case folding and requires exactly one;
9. explicitly deletes the temporary HKCU company **before** the product assertion, so panic-abort test profiles do not strand test state on an assertion failure;
10. retains a Drop cleanup guard for ordinary early `Result` returns.

The test is gated by Windows plus the repository's existing `test-windows-registry` feature. The whole `python_list` module is already gated by `test-python`, and Windows CI enables both features.

Expected discriminator:

- baseline should fail with two case-equivalent final rows if PATH and registry both reach the listing boundary;
- candidate should pass with one row;
- if baseline does not produce two rows, the captured stdout/stderr and source chain must identify which discovery source was filtered instead of treating the run as candidate evidence.

The fixture does not assert which spelling survives, only that one case-equivalent queried path remains. Host-installed registry Pythons do not affect that count because the assertion is scoped to the controlled executable path.

## Retained semantic boundary

Do **not** replace lexical comparison with file-identity deduplication. Distinct symlink, shim, registry, and search-path entries can be meaningful provenance. A repair should collapse only queried paths equal under Windows ordinal case-insensitive semantics while preserving genuinely distinct discovery entries.

The retained design sketch uses `CompareStringOrdinal` over UTF-16 through `uv-windows`, with unchanged non-Windows behavior. Its direct control also preserves a genuinely distinct shim path. It remains **unexecuted** against the new cross-source baseline.

## Execution gate

Before a new read-only Windows carrier is authoritative, static review must still confirm:

- the registry fixture compiles on the exact immutable base;
- the selected search-path executable is guaranteed to participate in 3.12 discovery on the test runner;
- explicit cleanup succeeds before any expected baseline assertion failure;
- the candidate's four-file product/test fence remains exact;
- the direct distinct-shim negative control runs with the candidate;
- no product source is published by the carrier.

No product source has been materialized. This packet is not an upstream contribution claim.
