# Self-review — uv extracted-wheel cache recovery

## Review subject

- Owned carrier: `teamleaderleo/uv#1`
- Exact public source pin: `astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`
- Narrow candidate: `missing-local-archive-candidate.patch`
- Main candidate transformations:
  - `apply_manifest_archive.py`
  - `apply_manifest_record.py`
  - `apply_manifest_export.py`
  - `apply_manifest_database.py`
- Public interaction: none

## Existing work checked

### Public upstream

- Open issue `astral-sh/uv#16841` records cache entries with zero-byte extracted wheel files and successful recovery after bypassing or clearing the cache.
- Closed PR `astral-sh/uv#19562` checked only for a non-empty `.dist-info/METADATA` file.
- Maintainer review rejected that as an incomplete cache-invalidation repair.
- No broader open public repair was found in issue, pull-request, commit, and code searches refreshed on 2026-08-03.
- Public `main` remained `79bbface771210df216b738e9bdc7df95e5a9e6b` at the final freshness check.

### Owned work

- The historical target-native probe reproduces reuse of zero-byte metadata and corrupted package code.
- A later one-line candidate added `Archive::exists()` only inside `DistributionDatabase::load_wheel()`.
- Exact execution showed that candidate did not run on the failing path: `Planner::build()` admitted the stale `.rev` pointer first and returned a missing archive path.
- The original carrier workflow also built the historical research base while describing the result as current-main execution.

## Candidate A — missing archive targets

### Repair

The revised three-file candidate:

1. makes the existing `Archive::exists()` helper callable by the installer crate;
2. checks it in the manual HTTP, local-path, and Git-path pointer branches of `Planner::build()`;
3. keeps the downstream `load_wheel()` check because planner rejection routes local and Git wheels back through that function.

The planner check prevents installation from being planned from a missing target. The downstream check prevents the same stale pointer from being accepted again during reconstruction.

### Exact source file fence

- `crates/uv-distribution/src/archive.rs`
- `crates/uv-distribution/src/distribution_database.rs`
- `crates/uv-installer/src/plan.rs`

### Review result

- no serialized cache-format change;
- no CLI, dependency, lockfile, or generated-source change;
- local and HTTP reversing probes are present;
- exact source identity and exact file inventory are fail-closed;
- successful execution publishes only `fix/missing-extracted-wheel-archive-recovery` in the owned fork.

### Limits

- existence checks are snapshots;
- arbitrary external deletion after validation remains possible;
- Git-path and Windows execution remain desirable;
- source-built/link-only wheel families use a different cache authority path and are outside this patch.

## Candidate B — present-but-corrupt extracted archives

### Repair

The five-file candidate builds on Candidate A and adds a backward-compatible optional member receipt to newly serialized wheel pointers.

During trusted extraction it retains:

- normalized member path;
- final uncompressed size, including the healed `RECORD` size.

At reuse `Archive::exists()`:

1. checks archive format version and directory presence;
2. preserves legacy-pointer behavior when no member receipt exists;
3. walks new-generation archives without following links;
4. rejects I/O errors, non-file entries, missing members, unexpected members, and size mismatches;
5. lets the existing local or HTTP refresh path create a new immutable archive generation.

### Exact source file fence

- `crates/uv-distribution/src/archive.rs`
- `crates/uv-distribution/src/distribution_database.rs`
- `crates/uv-install-wheel/src/lib.rs`
- `crates/uv-install-wheel/src/wheel.rs`
- `crates/uv-installer/src/plan.rs`

### API review correction

An early transformation changed the return type of public `validate_and_heal_record`. That was rejected during self-review.

The current candidate preserves the existing function and adds `validate_and_heal_record_with_manifest` as an additive helper used by `uv-distribution`.

### Expected reversing controls

- current source: clean archive remains healthy;
- current source: zero-byte `METADATA` is reused and fails;
- current source: size-changing package-code corruption is reused and fails;
- candidate: both corrupt cases create a separate healthy immutable generation and install successfully;
- candidate: local and HTTP missing-target controls continue to recover;
- focused `uv-distribution`, `uv-install-wheel`, and `uv-installer` tests pass;
- successful execution publishes only `fix/validate-extracted-wheel-cache-members` in the owned fork.

### Compatibility and correctness limits

- Legacy pointers contain no independent member receipt and retain existing behavior. This prototype protects newly created entries; it does not automatically heal every already-corrupt legacy cache.
- Path-and-size validation catches the reported zero-byte, missing, extra, and truncation class. It does not detect same-size content alteration.
- Full CRC or cryptographic verification requires reading member bodies and remains a separately benchmarked alternative.
- The mutable extracted `RECORD` is not reused as sole authority. The receipt is generated from trusted extraction output and stored in the independently serialized pointer.
- Walking every member adds warm-cache metadata cost. Performance measurement is required before upstream selection.
- Symlink or other non-file archive members are rejected by this prototype. Supported `.whl.zst` and unusual-wheel behavior must be checked before promotion.
- Existing orphan archive generations remain for normal cache cleanup after successful replacement.
- Source-built/link-only cache families remain outside the pointer-manifest claim.

## Workflow review

Both workflows now:

- check out the carrier only for probes and transformations;
- separately check out `fieldwork/upstream-79bbface`;
- assert the exact public source commit;
- retain exact tested patches and JSON receipts;
- fail if changed target files differ from the declared fence;
- publish clean source-only branches only after every focused gate passes.

The manifest workflow runs rustfmt before enforcing the five-file fence, so formatting output is part of the exact reviewed candidate rather than a handwritten transformation assumption.

## Current disposition

- Candidate A, missing targets: `EXECUTE`.
- Candidate B, new-generation member manifest: `EXECUTE`.
- Eligible upstream proposal: `REPAIR` until exact runs, artifact review, performance evidence, legacy policy, and platform controls are complete.
