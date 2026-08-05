# Fieldwork: Windows path-case duplicates in `uv python list`

Observed upstream report: https://redirect.github.com/astral-sh/uv/issues/13505  
Related completed report: https://redirect.github.com/astral-sh/uv/issues/9979  
Related historical change: https://redirect.github.com/astral-sh/uv/pull/12628  
Inspected fork head: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`  
External contact: **not authorized and not performed**

## Current classification

`EXECUTION PREPARED — final-stage dedup regression; Windows baseline/candidate matrix required`

The historical fix intentionally changed `uv python list` to display the queried executable path (`Interpreter::real_executable`) rather than Python's resolved `sys.executable`. That preserves useful information about shims and search-path entries.

The current listing command collects those queried paths and then removes duplicates with an `FxHashSet<PathBuf>`. Rust path equality is lexical and case-sensitive, so two Windows spellings such as `C:\Python312\python.exe` and `c:\python312\python.exe` survive as separate rows even though Windows resolves their casing equivalently.

## Semantic boundary

Do **not** replace the lexical check with file-identity deduplication. The earlier discussion explicitly keeps distinct symlink, shim, and search-path entries visible because the path used to reach an interpreter is relevant information. The narrow requirement is:

- on Windows, collapse queried paths that are equal under Windows ordinal case-insensitive comparison;
- on non-Windows platforms, preserve current exact path equality;
- preserve genuinely distinct shim, symlink, and search-path entries;
- avoid filesystem canonicalization and lossy UTF-8 conversion.

## Selected candidate

The workspace already enables the `windows` crate's `Win32_Globalization` feature, and the exact pinned `windows` 0.61 API exposes `CompareStringOrdinal(&[u16], &[u16], true)` plus `CSTR_EQUAL`.

`apply_candidate.py` therefore prepares:

1. `uv_windows::path_eq_ignore_case`, a lexical UTF-16 ordinal comparison wrapper;
2. Windows-only seen-path tracking that scans the small set of previously listed queried paths with that helper;
3. the existing hash-set behavior unchanged on non-Windows platforms;
4. a direct Unicode/ASCII case control that also preserves a distinct shim path;
5. an end-to-end extension of `python_list_duplicate_path_entries` that adds case-varied spellings of the same real interpreter directories.

The candidate does not canonicalize, resolve, or compare file identity.

## Execution contract

A read-only Windows carrier must prove:

- baseline plus the new integration control fails after compiling and running the focused test;
- candidate direct ordinal-comparison control passes;
- candidate integration control lists each interpreter once;
- `cargo fmt --check` and `git diff --check` pass;
- only the four expected source/test paths change locally;
- no product source is published by the carrier.

Only a green matrix permits materializing a clean owned-fork source branch. This packet is not an upstream contribution claim.
