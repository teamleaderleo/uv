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
