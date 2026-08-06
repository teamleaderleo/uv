# Fieldwork desk

Last refreshed: 2026-08-06

This is the review surface for completed evidence and decisions. Work does not move here until its claim, exact source identity, execution receipt, and remaining limits are written down.

## Ready for review

### UV local-directory lock provenance

**Finding:** The relative-path regression is broader than editable Poetry dependencies. UV 0.10.10 and 0.12.1 make both the child package source and the parent metadata path absolute for editable and non-editable local directories; UV 0.10.0 keeps them relative.

**Primary note:** `fieldwork/source-provenance-probe/FINDINGS.md`

**Baseline receipt:** run `30752194973`, generated merge `00ee711a4e5ac995adf70529f3fa66357f067967`.

**Decision:** Confirmed finding. No dependency-order or cold/warm nondeterminism was demonstrated.

### Exact draft `uv-dev#304` boundary

**Finding:** Exact draft `675839b0b1b1c66ee3b02139e1237094722ec2b2` fixes all four editable observations and leaves all four non-editable observations absolute.

**Receipt:** run `30930801134`, job `92064683893`, artifact `8903364962`, ZIP SHA-256 `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`.

**Decision:** The draft is incomplete for ordinary non-editable directories.

### Spelling-only repair experiment

**Finding:** A one-file “relative directory spelling wins; editability merges independently” candidate fixed all eight issue observations.

**Receipt:** run `30969832800`, job `92191555060`, artifact `8916217206`, ZIP SHA-256 `a631be2fb7773030e5e031b759e49e48f95c86973d528301e616890fd8f0ba97`.

**Decision:** Rejected as final policy. It can override intentional absolute root input because lookahead requirements are considered before root requirements.

### `RequirementOrigin` repair experiment

**Finding:** The candidate built and preserved the editable half, but it did not fix the non-editable half. All four non-editable package-source and parent-metadata observations remained absolute.

**Receipt:** run `30971266038`, job `92195886434`, artifact `8917108456`, ZIP SHA-256 `c2740df77257e0ce615d4ec8aed5d347e2d0d21d5f5c34f5186df917e9daa43e`.

**Additional classification:** The metadata-exact negative control was invalid because Core Metadata parsing rejects `child @ file:../child` without a working directory. Repository CI also found only a Prettier failure in `FINDINGS.md`; Rust and Python formatting passed.

**Decision:** `origin.is_some()` is not a sufficient root-versus-lookahead authority signal for this path. Replace it with explicit iterator-level provenance rather than expanding the heuristic.

## Active work

### Iterator-level root versus lookahead provenance

Preserve the existing requirement ordering, but carry an explicit collection-local authority tag from `Manifest` into `Urls::from_manifest`:

- lookahead metadata;
- root/workspace requirements;
- user constraints;
- overrides on their existing separate path.

The next candidate must repair the non-editable matrix while preserving intentionally absolute root input. No result is claimed yet.

### Deferred discriminators

- Symlink aliases: resource equality uses filesystem identity, while metadata repair currently keys exact install paths.
- Two origin-free local parents with conflicting spellings.
- Root requirements versus constraints and group-scoped sources.
- Direct-resolution and lock-based `pylock.toml` directory export parity.
- Existing-lock relocking, Windows drive and UNC paths, and local archives.

## External-contact boundary

No Astral issue, pull request, comment, review, reaction, email, or other upstream interaction is authorized or has been performed. Fork-only research may continue; upstream contact requires an explicit decision.
