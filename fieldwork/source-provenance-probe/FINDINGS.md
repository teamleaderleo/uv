# UV local-source provenance research

Date: 2026-08-05  
State: `FINDING CONFIRMED; ROOT-VS-LOOKAHEAD REPAIR UNDER EXECUTION; UPSTREAM CONTACT NOT AUTHORIZED`

Exact original upstream base:
`astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`.

Current focused carrier:
`teamleaderleo/uv#40` at `93b930ba940dc0ae5f84a774aa35baa87658a043`.

Completed carriers #11, #27, #37, and #38 are closed without merge. Their branches and receipts remain preserved.

## Confirmed regression

The bug reported as “relative editable paths become absolute through a transitive Poetry dependency” is a broader local-directory provenance regression.

When a root project selects a local child directory through a relative `[tool.uv.sources]` path, and a local parent emits an equivalent absolute path dependency in metadata, uv 0.10.10 and 0.12.1 serialize the child as absolute in both:

1. the child package `source` entry;
2. the parent package `requires-dist` metadata entry.

The same failure occurs for editable and non-editable directories. uv 0.10.0 keeps both representations relative.

## Release matrix receipt

Workflow run: `30752194973`  
Generated merge: `00ee711a4e5ac995adf70529f3fa66357f067967`

| uv | editable | non-editable | dependency order | cold/warm |
| --- | --- | --- | --- | --- |
| 0.10.0 | 0/4 source and 0/4 metadata absolute | 0/4 source and 0/4 metadata absolute | invariant | invariant |
| 0.10.10 | 4/4 source and 4/4 metadata absolute | 4/4 source and 4/4 metadata absolute | invariant | invariant |
| 0.12.1 | 4/4 source and 4/4 metadata absolute | 4/4 source and 4/4 metadata absolute | invariant | invariant |

Artifacts:

| uv | artifact | ZIP SHA-256 |
| --- | ---: | --- |
| 0.10.0 | `8834793365` | `a909d2961705d226cadbf08587b8ced337ef81557203480c885fa6f8541d2941` |
| 0.10.10 | `8834792931` | `5dccfdfaa039aecc71c87c66ac86deb2e9d3420e6790d7b85bd66e12578f8256` |
| 0.12.1 | `8834793219` | `58cac6f794e65adc8194869cb7423139035a9671f16348217953f8a5bdb72d4b` |

No executed order/cache matrix supports a nondeterminism claim.

## Exact draft #304 boundary

Public issue `astral-sh/uv#20477` is represented by private draft `astral-sh/uv-dev#304` at exact head `675839b0b1b1c66ee3b02139e1237094722ec2b2`.

Exact receipt:

- carrier head: `1f7a809966f0f7689ba0245ec20215ee83ceb8d3`;
- workflow run: `30930801134`;
- job: `92064683893`;
- artifact: `8903364962`;
- artifact ZIP SHA-256: `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`.

| mode | source | parent metadata |
| --- | --- | --- |
| editable, 4 observations | all relative | all relative |
| non-editable, 4 observations | all absolute | all absolute |

The draft fixes the reported editable case but not the ordinary non-editable sibling.

An early retained copy lacked a semicolon. The currently retained exact draft includes it and builds; that syntax failure is historical execution context, not a current defect in `675839b0...`.

## Why draft #304 stops at editability

The draft preserves a relative selected URL only through an editable-specific merge branch. Its lock serializer repairs generated metadata only when the selected distribution still carries a relative `VerbatimUrl`.

In the non-editable collision, URL selection can discard the root-relative spelling first. The serializer then sees an absolute selected distribution, excludes it from `relative_sources`, and cannot reconstruct the lost intent.

Resource identity, install mode, and presentation authority are separate properties.

## Completed spelling-only experiment

Fork PR #37 tested “relative directory spelling wins; editability merges independently.”

Exact successful receipt:

- head: `de93ecfc9e71af8ec15383beb287d320f38426ce`;
- generated merge: `56fb08842285b31145b61a0cc029618e12514269`;
- run: `30969832800`;
- job: `92191555060`;
- artifact: `8916217206`;
- ZIP SHA-256: `a631be2fb7773030e5e031b759e49e48f95c86973d528301e616890fd8f0ba97`.

It produced zero absolute source or metadata records across all eight observations and preserved editable state.

It is rejected as a final policy. `Manifest::requirements_no_overrides` emits lookahead requirements before root requirements. Universal relative precedence can therefore preserve generated relative metadata over an explicitly absolute root declaration, violating behavior established by `astral-sh/uv#18176`.

## Current root-versus-lookahead candidate

`Requirement` already carries `origin: Option<RequirementOrigin>`.

The source trace shows:

1. root/workspace lowering assigns a requirement origin;
2. built metadata requirements ordinarily enter lookahead without that root/file origin;
3. lookahead forwards lowered metadata requirements into `RequestedRequirements`;
4. `Manifest` flattens lookahead before root requirements;
5. `Urls::from_manifest` discards `requirement.origin` when it stores only `VerbatimParsedUrl`.

PR #40 retains `origin.is_some()` beside each URL during collection. For equivalent local directories it lets root/file-context spelling beat origin-free lookahead spelling, while merging editability independently. Equal-authority and override behavior remain on their existing paths; the sidecar is removed before downstream interfaces.

This is deliberately narrower than “all authored input wins.” A transitive local project’s explicit `tool.uv.sources` can lower a metadata requirement while its public requirement origin remains unset.

### Active execution

- fork PR: `teamleaderleo/uv#40`;
- head: `93b930ba940dc0ae5f84a774aa35baa87658a043`;
- generated merge: `00031f058443bd64cd6c7fca82de959ac09a3b07`;
- Fieldwork run: `30971266038`;
- job: `92195886434`;
- current state at this checkpoint: queued; no result claimed.

The run builds exact draft #304 plus the root-context sidecar and executes:

1. the unchanged eight-case editable/non-editable/order/cache matrix;
2. a metadata-exact negative control where the root declares `child` absolutely and a dependency-free backend emits `Requires-Dist: child @ file:../child`.

The control preflight-verifies that exact metadata line and refuses a vacuous result.

Success requires:

- original issue matrix: all relative root declarations remain relative;
- authority control: the selected child package source remains explicitly absolute in both dependency orders;
- editability remains preserved;
- no dependency-order variance.

## Additional source boundaries recorded

### Symlink aliases

Directory equality accepts `same_file::is_same_file`, but draft #304 repairs parent metadata through exact `(name, install_path)` lookup. A relative alias and absolute real path can therefore merge as one source while failing the later exact metadata lookup. This is a source-supported hypothesis, not yet an executed finding.

### `pylock.toml`

Direct resolution-to-pylock export uses the selected distribution URL and `was_given_absolute()`. Lock-to-pylock export uses the source spelling stored in `uv.lock`. Directory provenance is therefore downstream of URL selection and lock serialization; a pylock-only relativizer would be too late. Local wheel/archive policy from issue #16299 remains separate.

### Live upstream state

Current public `main` still contains the original equivalent-URL replacement behavior. No independent public repair has landed in URL collection.

## Directions declined or deferred

- **Blind serializer relativization:** cannot distinguish intentional absolute root input after authority is lost.
- **Metadata-only repair:** leaves the child package source absolute.
- **Poetry-version hunting:** a dependency-free backend reproduces the relevant metadata shape.
- **Async nondeterminism claims:** unsupported by executed order/cache matrices.
- **Universal relative precedence:** passes the issue fixture but violates explicit-absolute authority.
- **A new broad provenance enum immediately:** existing `RequirementOrigin` is sufficient to test the first root-versus-lookahead boundary.
- **Symlink, Windows, archive, or pylock implementation first:** dominated by the unresolved root-authority rule.
- **A competing upstream patch:** Astral has an active draft and upstream contact is not authorized.

## Workflow hygiene repair

Baseline PR #11 and exact-draft PR #27 were closed after their receipts were preserved. Their Fieldwork workflows were made manual/skip-only so note commits no longer rerun captured matrices or repository-wide CI through those carriers. Focused execution remains in PR #40.

## Next probes after PR #40

If the root-context candidate passes:

1. rename overbroad internal `authored` wording to `root_context`;
2. add upstream-shaped non-editable and explicit-absolute regression coverage;
3. test two origin-free lookahead projects with conflicting spellings;
4. test root requirement versus constraint and group authority;
5. execute the symlink alias mismatch;
6. compare direct and lock-based pylock directory export;
7. test existing-lock relocking, Windows drive/UNC paths, and local archives.

If it fails, inspect the actual requirement origins at URL collection before adding a new authority model.

## External-contact state

No Astral issue, pull request, comment, review, reaction, email, or other upstream interaction has been created. All implementation and execution work remains in the fork.
