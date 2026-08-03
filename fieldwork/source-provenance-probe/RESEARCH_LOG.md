# UV source-provenance fieldwork log

State: ongoing research; upstream contact not authorized.

This log records not only successful findings, but also rejected, deferred, and still-unexamined directions. Each dated pass should distinguish executed evidence from inference.

## Reporting format

For every research pass, record:

1. **Question considered** — the concrete invariant, regression boundary, or alternative explanation.
2. **Why it matters** — expected portability, reproducibility, correctness, or security consequence.
3. **Evidence gathered** — exact repository commit, uv version, fixture, command or workflow run, and artifact receipt.
4. **Result** — confirmed, disproved, inconclusive, or blocked.
5. **Reasons to stop or defer** — duplication, active upstream ownership, low consequence, inaccessible environment, unstable reproduction, excessive scope, or a cheaper discriminating test.
6. **Not yet considered** — meaningful adjacent cases that remain untested.
7. **Next smallest probe** — the cheapest test capable of changing the current conclusion.

Do not turn a plausible mechanism into a finding without execution. Do not contact Astral or another upstream project without explicit authorization.

## 2026-08-03 — Provenance regression framing

### Confirmed

- The relative-path regression is not limited to editable Poetry dependencies.
- uv 0.10.0 keeps editable and non-editable local-directory paths relative.
- uv 0.10.10 and 0.12.1 serialize both classes as absolute paths in the child package source and parent metadata.
- The tested fixture is invariant under root dependency-order reversal and cold/warm reruns.
- Exact receipts and the full matrix are in `FINDINGS.md`; corrected workflow run: `30752194973`.

### Considered, then rejected as a current claim

- **Asynchronous lookahead completion causes nondeterministic lockfiles.**
  - Reason considered: metadata is collected through `FuturesUnordered`, and lookahead results feed URL selection order.
  - Reason rejected for now: the executed order/cache matrix produced stable normalized output. The mechanism remains plausible in a delayed multi-parent fixture, but no nondeterminism was demonstrated.

- **The issue is only about editability.**
  - Reason rejected: the non-editable sibling reproduces identically. Editability is not the governing boundary.

- **A normal upstream PR should be prepared immediately.**
  - Reason rejected: `astral-sh/uv#20477` already points to active private draft `astral-sh/uv-dev#304`. Duplicating implementation work would add noise. The useful contribution is presently independent validation of the broader invariant and gaps in the draft's test surface.

### Deferred with reasons

- **Apply private draft #304 and run the complete matrix.**
  - High value, but must be done on a fork-only branch with the exact draft commit. This is the next priority because it directly distinguishes a complete repair from a report-shaped patch.

- **Local archive/path distributions.**
  - Deferred until directory behavior against #304 is known. Archives use related provenance machinery, but testing them first would widen scope before resolving the closest sibling.

- **Symlink aliases.**
  - Important because resource equality may use `is_same_file` while the draft's provenance repair keys exact install paths. Deferred until the draft is applied; otherwise the baseline absolute-path failure masks the alias-specific question.

- **Explicit relative and explicit absolute declarations for the same resource.**
  - Deferred because expected policy is ambiguous. This needs a policy question—priority, conflict, or deterministic canonicalization—not merely a regression assertion.

- **`pylock.toml` parity.**
  - Deferred until `uv.lock` repair behavior is established. It is a serializer-consistency check, not the shortest discriminator for draft #304.

### Not yet considered

- Multiple local parents emitting equivalent child requirements through different build backends.
- Marker- or fork-specific local sources where equivalent resources are selected in separate resolver environments.
- Case-folding and path-normalization differences on Windows and macOS.
- Relative sources that cross workspace roots or use nested `..` segments.
- Whether an existing lockfile preference preserves or replaces the original provenance during relock.
- Whether metadata caching created by one project root can leak absolute provenance into a different checkout root.

### Next smallest probe

Apply exact draft `astral-sh/uv-dev#304@675839b0b1b1c66ee3b02139e1237094722ec2b2` to exact upstream base `79bbface771210df216b738e9bdc7df95e5a9e6b`, then rerun the existing editable/non-editable eight-observation matrix without changing the fixture. Stop and reassess before expanding scope if either package source or parent metadata remains absolute.

## 2026-08-03 — Exact draft #304 validation launched

### Question considered

Does exact draft `uv-dev#304@675839b0b1b1c66ee3b02139e1237094722ec2b2` repair the full confirmed directory class, including the untested non-editable sibling and both lockfile locations?

### Why this is the highest-value next probe

The answer determines whether the active draft implements the broader provenance invariant or only repairs the reported editable collision. Every archive, alias, serializer, and platform probe becomes easier to interpret after this boundary is known.

### Evidence and execution setup

- Re-read `FINDINGS.md` and this log before selecting the probe.
- Re-fetched draft #304 on 2026-08-03. It remains open, draft, one commit, head `675839b0b1b1c66ee3b02139e1237094722ec2b2`, with the same editable-only fixture and no comments.
- The fork already contains `draft-304-production.patch`, an exact production-code extraction of that draft, plus `.github/workflows/fieldwork-draft-304.yml`.
- The workflow applies the patch to exact upstream base `79bbface771210df216b738e9bdc7df95e5a9e6b`, builds `uv`, and runs the existing eight-observation fixture unchanged.
- A second read-only-source workflow was added as an independent execution route, pinned to the same draft head. It avoids modifying or contacting Astral.
- Direct local cloning was attempted and blocked by DNS resolution in the automation container. That environment failure says nothing about UV behavior; GitHub Actions remains the execution source of record.

### Considered and declined

- **Copy the entire draft repository state into the fork.** Declined because the exact production patch already exists and yields a smaller, auditable delta against the recorded base.
- **Change the fixture while validating the draft.** Declined because unchanged inputs preserve comparability with the 0.10.0, 0.10.10, and 0.12.1 receipts.
- **Begin archive or symlink testing during the same run.** Deferred because a remaining ordinary directory failure would dominate those narrower cases.
- **Treat the draft source inspection as proof.** Declined. The implementation appears broad enough to cover relative directory sources, while its URL-selection branch remains tailored to editable precedence. Execution decides the result.

### Result state

Probe launched. Confirmed behavioral result remains pending until the patched-binary workflow produces receipts. No upstream contact occurred.

### Still unconsidered

- Whether the draft preserves an explicitly absolute root source when transitive metadata points to the same resource.
- Whether exact-path matching in `relative_sources` survives symlink aliases or normalized path variants.
- Whether a non-Poetry backend emits equivalent absolute metadata and crosses the same boundary.
- Whether `pylock.toml` uses the repaired provenance or independently leaks the backend spelling.

### Next smallest probe

Read the patched-binary artifact and classify all eight observations. If editable and non-editable directory records both remain relative, move next to a symlink-alias fixture because `same_resource` accepts filesystem identity while draft metadata repair keys package name plus exact install path.
