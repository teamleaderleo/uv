# Fieldwork: Windows path-case duplicates in `uv python list`

Observed upstream report: https://redirect.github.com/astral-sh/uv/issues/13505  
Related completed report: https://redirect.github.com/astral-sh/uv/issues/9979  
Related historical change: https://redirect.github.com/astral-sh/uv/pull/12628  
Inspected fork head: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`  
External contact: **not authorized and not performed**

## Current classification

`REPRODUCER/DESIGN — plausible final-stage dedup regression; Windows execution still required`

The historical fix intentionally changed `uv python list` to display the queried executable path (`Interpreter::real_executable`) rather than Python's resolved `sys.executable`. That preserves useful information about shims and search-path entries.

The current listing command collects those queried paths and then removes duplicates with an `FxHashSet<PathBuf>`. Rust path equality is lexical and case-sensitive, so two Windows spellings such as `C:\Python312\python.exe` and `c:\python312\python.exe` survive as separate rows even though Windows resolves them to the same path.

## Important semantic boundary

Do **not** replace the lexical check with file-identity deduplication. The earlier discussion explicitly keeps distinct symlink/search-path entries visible because the path used to reach an interpreter is relevant information. The narrow requirement is:

- on Windows, collapse lexical path variants that differ only by Windows case rules;
- on non-Windows platforms, preserve current exact path equality;
- preserve genuinely distinct shim, symlink, and search-path entries.

## Candidate test

`candidate-test.patch` sketches a Windows-only regression test that places the same interpreter directory on the search path twice with different ASCII casing and expects one listed interpreter. It also keeps the existing Unix symlink controls unchanged.

## Open implementation question

A simple ASCII-folded key covers the reported drive/component casing but is not a complete implementation of Windows ordinal case-insensitive comparison for every Unicode path. Before selecting production code, prefer an existing repository/Windows helper or a small wrapper around the Windows ordinal comparison API. Avoid lossy UTF-8 conversion and avoid filesystem canonicalization that erases intentional symlink provenance.

## Stop condition

No production patch is selected until the regression test fails on a Windows runner and the chosen comparison preserves the existing symlink/shim behavior. This branch is an owned-fork investigation packet, not an upstream contribution claim.
