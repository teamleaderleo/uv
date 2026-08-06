# UV local-source provenance research

Date: 2026-08-06  
State: `FINDING CONFIRMED; ITERATOR-LEVEL AUTHORITY REPAIR NEXT; UPSTREAM CONTACT NOT AUTHORIZED`

Review index: `fieldwork/DESK.md`.

Exact original upstream base: `astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`.

## Confirmed regression

The bug reported as “relative editable paths become absolute through a transitive Poetry dependency” is a broader local-directory provenance regression.

When a root project selects a local child directory through a relative `[tool.uv.sources]` path, and a local parent emits an equivalent absolute path dependency in metadata, UV 0.10.10 and 0.12.1 serialize the child as absolute in both:

1. the child package `source` entry;
2. the parent package `requires-dist` metadata entry.

The same failure occurs for editable and non-editable directories. UV 0.10.0 keeps both representations relative.

### Release matrix receipt

- workflow run: `30752194973`;
- generated merge: `00ee711a4e5ac995adf70529f3fa66357f067967`;
- UV 0.10.0 artifact: `8834793365`, ZIP SHA-256 `a909d2961705d226cadbf08587b8ced337ef81557203480c885fa6f8541d2941`;
- UV 0.10.10 artifact: `8834792931`, ZIP SHA-256 `5dccfdfaa039aecc71c87c66ac86deb2e9d3420e6790d7b85bd66e12578f8256`;
- UV 0.12.1 artifact: `8834793219`, ZIP SHA-256 `58cac6f794e65adc8194869cb7423139035a9671f16348217953f8a5bdb72d4b`.

The corrected probe normalizes each disposable case root. Every executed dependency-order and cold/warm comparison was invariant. No executed evidence supports a nondeterminism claim.

## Exact draft `uv-dev#304` boundary

Public issue `astral-sh/uv#20477` is represented by draft `astral-sh/uv-dev#304` at exact head `675839b0b1b1c66ee3b02139e1237094722ec2b2`.

Exact execution:

- tested carrier head: `1f7a809966f0f7689ba0245ec20215ee83ceb8d3`;
- workflow run: `30930801134`;
- job: `92064683893`;
- artifact: `8903364962`;
- ZIP SHA-256: `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`.

Result:

- editable package sources: relative in `4/4` observations;
- editable parent metadata: relative in `4/4` observations;
- non-editable package sources: absolute in `4/4` observations;
- non-editable parent metadata: absolute in `4/4` observations.

The draft fixes the reported editable case but not its ordinary non-editable sibling.

An early retained copy lacked a semicolon. The currently retained exact draft includes it and builds. The syntax failure is historical execution context, not a defect in the retained head.

## Why the draft stops at editability

The draft preserves a relative selected URL through an editable-specific merge branch. Its lock serializer can repair generated metadata only when the selected distribution still carries a relative `VerbatimUrl`.

In the non-editable collision, URL selection can discard the root-relative spelling first. The serializer then sees an absolute selected distribution, excludes it from `relative_sources`, and cannot reconstruct the lost presentation intent.

Resource identity, install mode, and presentation authority are separate properties.

## Completed spelling-only experiment

Fork PR `teamleaderleo/uv#37` tested this rule after exact draft #304:

- equivalent local directories prefer the relative spelling;
- editability merges independently;
- non-directory URL behavior remains unchanged.

Exact successful receipt:

- candidate head: `de93ecfc9e71af8ec15383beb287d320f38426ce`;
- generated merge: `56fb08842285b31145b61a0cc029618e12514269`;
- workflow run: `30969832800`;
- job: `92191555060`;
- artifact: `8916217206`;
- ZIP SHA-256: `a631be2fb7773030e5e031b759e49e48f95c86973d528301e616890fd8f0ba97`.

It produced zero absolute package-source records and zero absolute parent-metadata records across all eight observations. All editable package sources remained editable.

The experiment is rejected as a final policy. `Manifest::requirements_no_overrides` emits lookahead requirements before root requirements. Universal relative precedence can therefore retain lower-authority relative input over an intentionally absolute root declaration.

## Rejected `RequirementOrigin` experiment

Fork PR `teamleaderleo/uv#40` retained `requirement.origin.is_some()` beside each URL during collection. For equivalent directories it attempted to let origin-bearing input outrank origin-free input while merging editability independently.

Exact execution:

- candidate head: `93b930ba940dc0ae5f84a774aa35baa87658a043`;
- generated merge: `00031f058443bd64cd6c7fca82de959ac09a3b07`;
- workflow run: `30971266038`;
- job: `92195886434`;
- artifact: `8917108456`;
- ZIP SHA-256: `c2740df77257e0ce615d4ec8aed5d347e2d0d21d5f5c34f5186df917e9daa43e`.

The patch applied, compiled, and completed the original eight-observation matrix.

Result:

- editable package sources and parent metadata remained relative in all `4/4` observations;
- non-editable package sources remained absolute in all `4/4` observations;
- non-editable parent metadata remained absolute in all `4/4` observations;
- dependency-order and cold/warm comparisons remained invariant.

Therefore `origin.is_some()` did not distinguish the root-relative non-editable declaration from the replacing lookahead requirement in this resolver path. It is not a sufficient authority signal for the repair.

### Invalid negative control

The accompanying custom backend emitted the exact metadata line:

```text
Requires-Dist: child @ file:../child
```

UV then correctly rejected that built metadata before resolution:

```text
relative path without a working directory: ../child
```

Core Metadata does not provide a working directory for that relative direct URL. The control is invalid and establishes no authority result.

A future control must use a source context that legitimately carries a relative path, such as local-project source lowering, and must separately prove the competing spellings reached URL collection.

### Repository CI classification

Rust formatting and Python formatting passed. Prettier failed only on the prior `FINDINGS.md` formatting. That documentation issue is separate from the semantic rejection above.

## Next repair direction

Do not add another spelling heuristic and do not broaden `RequirementOrigin` by intuition.

The next candidate should preserve provenance explicitly at the point where `Manifest` still knows the iterator lane. URL collection needs a collection-local authority tag that distinguishes at least:

- lookahead requirements;
- root or workspace requirements;
- user constraints;
- overrides, which remain on their existing separate replacement path.

The candidate should preserve the current requirement ordering and downstream URL interfaces. It should carry the authority tag only through equivalent-resource selection, merge editability independently, then drop the tag.

Required evidence:

1. the unchanged editable and non-editable issue matrix;
2. an intentionally absolute root-source control using a valid competing lower-authority source context;
3. proof that both competing spellings reached URL collection;
4. dependency-order invariance;
5. exact changed-file fencing and retained artifact receipts.

## Additional source boundaries

### Symlink aliases

Directory equality accepts `same_file::is_same_file`, while draft #304 repairs parent metadata through exact `(name, install_path)` lookup. A relative alias and an absolute real path can merge as one source while failing the later exact metadata lookup. This is a source-supported hypothesis, not an executed finding.

### `pylock.toml`

Direct resolution-to-pylock export uses the selected distribution URL and `was_given_absolute()`. Lock-to-pylock export uses the source spelling stored in `uv.lock`. Directory provenance is downstream of URL selection and lock serialization; a pylock-only relativizer would be too late.

Local wheel and archive export policy from issue `astral-sh/uv#16299` remains separate.

### Live upstream state

The inspected public `main` still contains the original equivalent-URL replacement behavior. No independent public repair had landed at the last check.

## Directions declined or deferred

- blind serializer relativization;
- metadata-only repair;
- Poetry-version hunting;
- asynchronous nondeterminism claims;
- universal relative precedence;
- treating `origin.is_some()` as authority;
- a broad provenance enum before iterator-level evidence;
- symlink, Windows, archive, or pylock implementation before the ordinary directory authority rule;
- a competing upstream patch while Astral has an active draft and upstream contact is not authorized.

## External-contact state

No Astral issue, pull request, comment, review, reaction, email, or other upstream interaction has been created. All implementation and execution work remains in the fork.
