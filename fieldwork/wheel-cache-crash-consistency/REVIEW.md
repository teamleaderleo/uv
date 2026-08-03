# Self-review — uv extracted-wheel cache recovery

## Review subject

- Owned carrier: `teamleaderleo/uv#1`
- Current public source pin: `astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`
- Candidate patch: `missing-local-archive-candidate.patch`
- Public interaction: none

## Existing work checked

### Public upstream

- Open issue `astral-sh/uv#16841` records cache entries with zero-byte extracted wheel files and successful recovery after bypassing or clearing the cache.
- Closed PR `astral-sh/uv#19562` checked only for a non-empty `.dist-info/METADATA` file.
- Maintainer review rejected that as an incomplete cache-invalidation repair.
- No broader open public repair was found in issue, pull-request, and code searches performed on 2026-08-03.

### Owned work

- The historical target-native probe reproduces reuse of zero-byte metadata and corrupted package code.
- A later one-line candidate added `Archive::exists()` only inside `DistributionDatabase::load_wheel()`.
- Exact execution showed that candidate did not run on the failing path: `Planner::build()` admitted the stale `.rev` pointer first and returned a missing archive path.

## Corrections made during this review

### 1. Repair both cache gates

The revised candidate:

1. makes the existing `Archive::exists()` helper callable by the installer crate;
2. checks it in the manual HTTP, local-path, and Git-path pointer branches of `Planner::build()`;
3. keeps the downstream `load_wheel()` check because planner rejection routes local and Git wheels back through that function.

The planner check prevents installation from being planned from a missing target. The downstream check prevents the same stale pointer from being accepted again during reconstruction.

### 2. Bind execution to current public source

The original carrier workflow built the research branch's historical base while describing the result as current-head execution. The repaired workflow now:

- checks out the owned carrier only for probes and patches;
- separately checks out `fieldwork/upstream-79bbface`;
- asserts that source checkout is exactly `79bbface771210df216b738e9bdc7df95e5a9e6b`;
- applies the candidate only inside that checkout;
- records the exact three-file tested diff.

## Complete candidate file fence

- `crates/uv-distribution/src/archive.rs`
- `crates/uv-distribution/src/distribution_database.rs`
- `crates/uv-installer/src/plan.rs`

No dependency, lockfile, generated file, documentation, or workflow belongs in the eventual source-only branch.

## Correctness review

### Supported behavior

- A `.http` or `.rev` pointer whose archive ID no longer exists is not admitted as an installable cached wheel.
- Local and Git path wheels re-enter `load_wheel()`, where the stale pointer is checked again before reuse.
- HTTP wheels re-enter the existing refresh path, which already checks `Archive::exists()` before returning the cached response.
- Archive-version rejection remains centralized in `Archive::exists()`.

### Race limit

Existence checks are snapshots. Another process can remove an archive after a check. The cache root lock is intended to prevent `uv cache` cleaning during active operations, but arbitrary external deletion remains possible. The downstream local/Git check narrows the window; this candidate does not claim protection from hostile concurrent filesystem mutation.

### Compatibility

- No serialized cache format changes.
- No CLI or public Python-facing API changes.
- `Archive::exists()` becomes public across internal workspace crates; its documentation and semantics are unchanged.
- Legacy cache pointers retain their current behavior when the target directory exists.

## Test review

Required exact controls:

1. current source reproduces the missing local archive failure;
2. candidate re-extracts from the unchanged local wheel;
3. replacement uses a new archive identity;
4. stale pointer bytes do not survive unchanged;
5. original wheel bytes remain unchanged;
6. focused `uv-distribution` and `uv-installer` tests pass;
7. candidate diff has exactly the three source files above.

Still desirable before upstream packaging:

- direct-URL HTTP missing-archive recovery;
- Git-path wheel missing-archive recovery;
- Windows execution;
- a target-native Rust integration test instead of retaining the Python probe as the only reversing control.

## Scope judgment

This candidate fixes **missing archive targets**. It does not fix the main present-but-corrupt case from issue `#16841`, because `Archive::exists()` still accepts an existing directory without validating its members.

The broader repair should persist an independent trusted member manifest during extraction and validate it before reuse. The extracted archive's mutable `RECORD` is not sufficient authority by itself. Full content verification also needs a measured performance decision.

## Current disposition

`EXECUTE`

Promote the missing-target candidate only after exact current-head execution passes. Keep the present-but-corrupt archive repair in `REPAIR` until a manifest candidate and performance controls exist.
