# Fieldwork checkpoint — draft #304 boundary

Date: 2026-08-05  
State: confirmed execution result; fork-only repair candidate in progress; upstream contact not authorized.

## Question considered

Does exact draft `astral-sh/uv-dev#304@675839b0b1b1c66ee3b02139e1237094722ec2b2` repair the full local-directory provenance regression, or only the reported editable case?

## Exact evidence

Execution carrier: `teamleaderleo/uv#27`  
Carrier head tested: `1f7a809966f0f7689ba0245ec20215ee83ceb8d3`  
Workflow run: `30930801134`  
Job: `92064683893`  
Artifact: `8903364962`  
Artifact ZIP SHA-256: `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`

The workflow applied the exact retained draft, fenced its production/test diff to the three upstream files, built `uv`, put that binary first on `PATH`, and ran the unchanged eight-observation matrix.

## Result

The draft fixes the editable half and leaves the non-editable half unchanged.

| mode | observations | child source | parent metadata |
| --- | ---: | --- | --- |
| editable | 4 | all relative | all relative |
| non-editable | 4 | all absolute | all absolute |

Dependency order and cold/warm cache state remained invariant. This result does not support a nondeterminism claim.

## Corrected chronology

An earlier retained copy of the draft lacked a semicolon and failed compilation. The currently retained exact draft already contains that semicolon and builds without an additional source repair. The syntax failure is historical execution context, not a current defect in draft head `675839b0...`.

## Why the non-editable half remains broken

The draft has two linked parts:

1. URL selection preserves an existing relative URL only through an editable-specific branch.
2. Lock serialization builds `relative_sources` only from selected directory distributions whose surviving `VerbatimUrl` is relative.

For the non-editable collision, equivalent generated metadata can still replace the relative root URL with an absolute URL. The selected distribution is therefore absolute, it is absent from `relative_sources`, and the metadata-repair helper has no signal to act on. The serializer cannot recover provenance that URL selection already discarded.

This narrows the repair boundary: editability and presentation provenance must be merged independently. A local directory can need relative presentation without being editable.

## Directions considered and declined

### Blindly relativize every absolute directory during lock serialization

Declined. An explicitly absolute root declaration may be intentional. Serialization cannot safely infer user intent from resource identity alone after provenance has been discarded.

### Change only the metadata-repair helper

Declined. The child package source itself is already absolute in the failing non-editable cases. A metadata-only change would leave half of the observable regression intact.

### Add only a non-editable regression test

Insufficient by itself. The executed matrix already proves the failure; the next useful step is a narrowly fenced repair candidate plus the same unchanged test input.

### Expand immediately to archives, symlinks, or `pylock.toml`

Deferred. Ordinary non-editable directories still fail, so broader aliases and serializers would be dominated by the simpler unresolved boundary. Those probes become discriminating after directory selection is repaired.

### Pursue asynchronous ordering as the primary explanation

Deferred. Both the release matrix and exact-draft matrix were invariant under the tested order and cache permutations. A delayed multi-parent fixture is required before making that claim.

### Prepare or post an upstream patch

Declined. Astral already has an active draft, and upstream contact is not authorized. All repair work remains fork-only research.

## Repair candidate selected

Branch: `research/generalize-uv-dev-304-noneditable-20260805`

The candidate applies after exact draft #304 and changes only equivalent local-directory URL merging:

- preserve an existing relative directory spelling when the incoming equivalent spelling is absolute;
- preserve editability independently by OR-ing the editable state across the equivalent pair;
- otherwise retain the draft's replacement behavior;
- leave non-directory URLs untouched.

This is intentionally narrower than introducing a new provenance type. It tests whether the missing policy is specifically “relative directory presentation wins while editability is merged separately.”

## Not yet considered

- explicit relative and explicit absolute root declarations for the same resource, where policy may need conflict detection rather than precedence;
- symlink aliases where `same_resource` succeeds through filesystem identity but metadata repair keys exact install paths;
- `pylock.toml` serialization parity;
- multiple parents or build backends emitting different equivalent spellings;
- Windows path case-folding and drive/UNC behavior;
- relocking from an existing lockfile carrying stale absolute provenance;
- local archive/path distributions.

## Next smallest probe

Build exact draft #304 plus the one-file URL-selection candidate, then rerun the unchanged eight-observation matrix. A credible result requires zero absolute child-source records and zero absolute parent-metadata records while retaining all four editable sources as editable.
