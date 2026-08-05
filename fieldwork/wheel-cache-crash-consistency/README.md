# uv extracted-wheel cache recovery

## Current disposition

This lane contains two separate candidates. Their evidence and promotion decisions must not be combined.

### Candidate A — missing archive target

**Disposition: `POLISH / CURRENT-MAIN RERUN`**

A cached `.http` or `.rev` pointer can remain valid-looking after its `archive-v0/<id>` directory disappears. Candidate A rejects those stale pointers before planner admission and rechecks local/Git pointers during reconstruction so uv returns through its existing download or extraction path.

Current source boundary:

- `crates/uv-distribution/src/archive.rs`;
- `crates/uv-distribution/src/distribution_database.rs`;
- `crates/uv-installer/src/plan.rs`;
- `crates/uv/tests/pip/pip_sync.rs`.

The fourth file is a repository-native regression. It installs a downloaded local wheel, deletes only the selected extracted archive generation, recreates the environment, and requires successful re-extraction from byte-identical source wheel data into a new generation.

Executed evidence already includes:

- Linux local and HTTP baseline reproduction and candidate recovery;
- Windows local-wheel baseline reproduction and candidate recovery;
- unchanged source wheel bytes;
- stale pointer replacement;
- focused source crate tests.

The current native-regression carrier and clean-source republish are queued. After they pass, Candidate A should be reconciled onto current public main and reviewed as its own small contribution.

### Candidate B — present but corrupt archive

**Disposition: `REPAIR / MEASURE`**

The five-file prototype records an optional normalized member-path and uncompressed-size receipt in newly created wheel pointers. On reuse, `Archive::exists` walks the extracted archive without following links and rejects missing members, unexpected members, non-file entries, size mismatches, and missing targets.

Source boundary:

- `crates/uv-distribution/src/archive.rs`;
- `crates/uv-distribution/src/distribution_database.rs`;
- `crates/uv-install-wheel/src/lib.rs`;
- `crates/uv-install-wheel/src/wheel.rs`;
- `crates/uv-installer/src/plan.rs`.

Run `30945457187` completed successfully at carrier head `87abbfac14ebf4fc8db952c8bf9142511dffea6f`. It compiled the candidate, reproduced metadata-zero and package-module corruption, created fresh healthy archive generations for both corrupt cases, recovered local and HTTP missing targets, passed focused tests, and published clean source head `9ba8aeb5f73a77639f01bb2ec53dbae2ddb4008b`.

The original probe called healthy republishing `inconclusive` whenever the old corrupt immutable generation remained as an orphan. The classifier now distinguishes authoritative healthy republishing from physical orphan deletion.

The source generator also carries native tests for a valid receipt, a missing member, an unexpected member, a size mismatch, and legacy pointer deserialization without a receipt. Stricter execution is queued.

## Active evidence lanes

- Candidate A final native-regression run and clean republish;
- Candidate B stricter recovery and native-test run;
- warm-cache benchmark at 100, 1,000, and 5,000 members, recording medians and ratios without a noisy threshold;
- deterministic target test replaying a legal publication interleaving where the wheel-entry link and `.rev` pointer name different archive generations.

## Remaining design gates

Candidate B is not ready for public promotion until these are resolved:

1. **Performance:** every validated cache hit walks the extracted member tree. Compare the simple preflight design with validation during installation if measured overhead is meaningful.
2. **Generation authority:** ordinary Unix publication writes the wheel-entry link and `.http` / `.rev` pointer separately. The deterministic interleaving test will establish whether one generation can become pointer-authoritative while another is GC-authoritative.
3. **Coverage:** source-built/link-only wheels have no `Archive` pointer for this receipt. `.whl.tar.zst` can contain Unix symlinks that the current walk rejects. Broader Git-path and Windows content controls remain.
4. **Integrity level:** path and size detect the confirmed accidental corruption classes but not same-size alteration. CRC32 or cryptographic member digests require reading member bodies and need a separate cost decision.
5. **Mutation window:** validation is a snapshot. External mutation after validation but before or during installation remains possible.
6. **Legacy behavior:** pointers created before this change contain no receipt and intentionally retain presence-only reuse semantics.

## Current source relationship

The source pin remains `0cf7c4561b7c7159ab9479719a12573d0a6aa3bb`. Public main advanced to `49e2fc5c821bb69a528308a036b17446bb5ab5a6`; the inspected 12-commit delta did not touch either candidate's product source fence. Rebase only after the current evidence shape stabilizes.

## Public overlap

- Public issue: `astral-sh/uv#16841`.
- Closed metadata-only attempt: `astral-sh/uv#19562`.
- No broader current public repair was found in the latest overlap search.

This branch and `teamleaderleo/uv#1` are owned research carriers. They are not public upstream proposals. No public action should be taken from this lane without a separate human decision.