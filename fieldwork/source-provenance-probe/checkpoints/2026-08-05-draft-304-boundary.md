# Fieldwork checkpoint — draft #304 boundary

Date: 2026-08-05  
State: exact draft boundary confirmed; generalized candidate passes the reported matrix but remains under an authority negative control; upstream contact not authorized.

## Question considered

Does exact draft `astral-sh/uv-dev#304@675839b0b1b1c66ee3b02139e1237094722ec2b2` repair the full local-directory provenance regression, or only the reported editable case?

## Exact draft evidence

Execution carrier: `teamleaderleo/uv#27`  
Carrier head tested: `1f7a809966f0f7689ba0245ec20215ee83ceb8d3`  
Workflow run: `30930801134`  
Job: `92064683893`  
Artifact: `8903364962`  
Artifact ZIP SHA-256: `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`

The workflow applied the exact retained draft, fenced its production/test diff to the three upstream files, built `uv`, put that binary first on `PATH`, and ran the unchanged eight-observation matrix.

## Exact draft result

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

Insufficient by itself. The executed matrix already proves the failure; the next useful step was a narrowly fenced repair candidate plus the same unchanged test input.

### Expand immediately to archives, symlinks, or `pylock.toml`

Deferred. Ordinary non-editable directories were the simpler unresolved boundary. Those probes become discriminating only after directory selection and explicit path authority are understood.

### Pursue asynchronous ordering as the primary explanation

Deferred. The release, exact-draft, and generalized-candidate matrices were invariant under the tested order and cache permutations. A delayed multi-parent fixture is required before making that claim.

### Prepare or post an upstream patch

Declined. Astral already has an active draft, and upstream contact is not authorized. All repair work remains fork-only research.

## Generalized repair candidate

Fork-only draft PR: `teamleaderleo/uv#37`  
Candidate branch: `research/generalize-uv-dev-304-noneditable-20260805`  
Exact tested head: `de93ecfc9e71af8ec15383beb287d320f38426ce`  
Generated merge tested: `56fb08842285b31145b61a0cc029618e12514269`  
Workflow run: `30969832800`  
Job: `92191555060`  
Artifact: `8916217206`  
Artifact ZIP SHA-256: `a631be2fb7773030e5e031b759e49e48f95c86973d528301e616890fd8f0ba97`

The candidate applies after exact draft #304 and changes only equivalent local-directory URL merging:

- preserve the relative directory spelling when the equivalent pair contains one relative and one absolute spelling;
- preserve editability independently by OR-ing the editable state across the equivalent pair;
- leave non-directory URLs untouched.

The first execution attempt failed before compilation because the stored diff hunk header declared 42 new lines while containing 39. The header was corrected without changing candidate logic, then the exact repaired head above was built and tested.

## Generalized candidate result

The candidate passed all eight unchanged observations:

| mode | observations | child source | parent metadata |
| --- | ---: | --- | --- |
| editable | 4 | all `editable = "../child"` | all `directory = "../child"` |
| non-editable | 4 | all `directory = "../child"` | all `directory = "../child"` |

Absolute child-source records: **0/8**.  
Absolute parent-metadata records: **0/8**.  
Dependency order and cold/warm cache state remained invariant.

This proves that URL selection is sufficient to extend draft #304 across the executed non-editable sibling. It does **not** yet prove that universal relative precedence preserves intentional absolute root declarations.

## Current risk and next probe

PR `astral-sh/uv#18176` explicitly tests that user-provided absolute paths remain absolute. Meanwhile, `Manifest` retains distinctions between project requirements and lookahead requirements, but `Urls::from_manifest` flattens those inputs before equivalent-resource merging and loses their authority.

The next probe is therefore not symlinks or another serializer. It is an authority conflict:

- root explicitly declares `child` by an absolute path;
- a local parent declares the same `child` through a relative `tool.uv.sources` path;
- run both dependency orders against draft #304 plus the generalized candidate;
- inspect package source and parent metadata separately.

A candidate that changes the explicit root declaration to relative is not acceptable even if it fixes issue #20477. That result would require an authority-aware merge rather than a spelling-only preference.

## Not yet considered

- constraints and overrides as competing URL authorities;
- symlink aliases where `same_resource` succeeds through filesystem identity but metadata repair keys exact install paths;
- `pylock.toml` serialization parity;
- multiple parents or build backends emitting different equivalent spellings;
- Windows path case-folding and drive/UNC behavior;
- relocking from an existing lockfile carrying stale absolute provenance;
- local archive/path distributions.
