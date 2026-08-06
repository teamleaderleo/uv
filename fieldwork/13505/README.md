# Fieldwork: Windows path-case duplicates in `uv python list`

Observed upstream report: https://redirect.github.com/astral-sh/uv/issues/13505  
Related completed report: https://redirect.github.com/astral-sh/uv/issues/9979  
Related historical change: https://redirect.github.com/astral-sh/uv/pull/12628  
Inspected fork base: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`  
External contact: **not authorized and not performed**

## Current classification

`SOURCE/HISTORY MAPPED — DUPLICATED-PATH REPRODUCER ABSENT — CANDIDATE UNEXECUTED`

The historical fix intentionally changed `uv python list` to display the queried executable path (`Interpreter::real_executable`) rather than Python's resolved `sys.executable`. That preserves useful information about shims and search-path entries.

The final listing command removes duplicate queried paths with an `FxHashSet<PathBuf>`. Rust path equality is lexical and case-sensitive, so the final-stage code can retain Windows case variants. The public reports, however, involve interpreters arriving through distinct discovery routes such as a direct path, registry entry, WindowsApps entry, or shim whose resolved spelling differs.

## Executed Windows result

Read-only carrier run `31047448111`, job `92446355170`, used packet `bef3a851268867f6c85cab49aa998471cc7af873` on Windows Server 2022.

The carrier:

- checked out the immutable baseline and candidate source;
- applied the UTF-16 case-variant integration control and candidate transformer cleanly;
- compiled the baseline successfully;
- ran exactly one focused `python_list_duplicate_path_entries` test;
- observed the baseline test **pass**, listing each Python once;
- skipped the candidate stage because the required baseline failure was absent.

Artifact `8948402487`, SHA-256 `a136314c4f7d4b21c7d29fdd105de187fb6faccedfd1d01815485964ea37aabc`, retains the baseline transcript.

This is not evidence that issue #13505 is fixed and not evidence for the candidate. It establishes that adding case-varied copies of the same directories to `UV_PYTHON_SEARCH_PATH` does not reproduce the report on the tested head. An earlier discovery layer already collapses or otherwise avoids those duplicates.

## Retained semantic boundary

Do **not** replace lexical comparison with file-identity deduplication. Distinct symlink, shim, registry, and search-path entries can be useful provenance. A repair should collapse only queried paths equal under Windows ordinal case-insensitive semantics while preserving genuinely distinct discovery entries.

The selected design sketch still uses `CompareStringOrdinal` over UTF-16 through `uv-windows`, with unchanged non-Windows behavior. It remains **unexecuted** because its end-to-end baseline control is invalid.

## Next discriminator

A renewed experiment must reproduce the public shape through two distinct discovery sources or isolate the final inclusion boundary directly.

Preferred controls:

1. PATH plus registry or shim discovery of one interpreter with case-varied queried paths;
2. a focused final-list unit that feeds two case-varied queried paths into the current inclusion logic and fails on the baseline;
3. a negative control preserving two genuinely distinct shim/search-path locations.

No new Windows carrier should run until one of those controls distinguishes the baseline. No product source has been materialized. This packet is not an upstream contribution claim.
