# UV local-source provenance research

Date: 2026-08-05  
State: `FINDING CONFIRMED; REPAIR POLICY UNDER TEST; UPSTREAM CONTACT NOT AUTHORIZED`

Internal carriers:

- baseline release matrix: `teamleaderleo/uv#11`;
- exact draft #304 validation: `teamleaderleo/uv#27`;
- generalized non-editable candidate: `teamleaderleo/uv#37`;
- absolute-root authority negative control: `teamleaderleo/uv#38`.

Exact original upstream base:
`astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`.

## Confirmed finding

The regression reported as “relative editable paths become absolute through a transitive Poetry dependency” is a broader local-directory provenance regression.

When a root project explicitly selects a local child directory through a relative `[tool.uv.sources]` path, and a local parent emits an equivalent absolute path dependency in generated metadata, uv 0.10.10 and 0.12.1 serialize the child as absolute in both of these places:

1. the child package `source` entry;
2. the parent package `requires-dist` metadata entry.

The same failure occurs for editable and non-editable local directories. uv 0.10.0 keeps both representations relative.

## Release matrix

Workflow run: `30752194973`  
Generated merge tested: `00ee711a4e5ac995adf70529f3fa66357f067967`

| uv | editable | non-editable | dependency order | cold/warm |
| --- | --- | --- | --- | --- |
| 0.10.0 | 0/4 source and 0/4 metadata absolute | 0/4 source and 0/4 metadata absolute | invariant | invariant |
| 0.10.10 | 4/4 source and 4/4 metadata absolute | 4/4 source and 4/4 metadata absolute | invariant | invariant |
| 0.12.1 | 4/4 source and 4/4 metadata absolute | 4/4 source and 4/4 metadata absolute | invariant | invariant |

Artifact receipts:

| uv | artifact | ZIP SHA-256 |
| --- | ---: | --- |
| 0.10.0 | `8834793365` | `a909d2961705d226cadbf08587b8ced337ef81557203480c885fa6f8541d2941` |
| 0.10.10 | `8834792931` | `5dccfdfaa039aecc71c87c66ac86deb2e9d3420e6790d7b85bd66e12578f8256` |
| 0.12.1 | `8834793219` | `58cac6f794e65adc8194869cb7423139035a9671f16348217953f8a5bdb72d4b` |

The corrected probe normalizes each disposable case root before comparing outputs. None of the executed matrices demonstrates dependency-order or cache-state nondeterminism.

## Exact active-draft boundary

Public issue `astral-sh/uv#20477` is represented by private draft `astral-sh/uv-dev#304` at exact head `675839b0b1b1c66ee3b02139e1237094722ec2b2`.

Exact-draft execution:

- carrier: `teamleaderleo/uv#27`;
- tested carrier head: `1f7a809966f0f7689ba0245ec20215ee83ceb8d3`;
- workflow run: `30930801134`;
- job: `92064683893`;
- artifact: `8903364962`;
- artifact ZIP SHA-256: `4260448eb9334622e737435d55e33ebb39addfb2c1bb2f73b675cba5eff1b3c7`.

Result:

| mode | source | parent metadata |
| --- | --- | --- |
| editable, 4 observations | all relative | all relative |
| non-editable, 4 observations | all absolute | all absolute |

The draft therefore repairs the reported editable case but not the ordinary non-editable sibling.

An early retained copy failed to compile because it lacked a semicolon. The currently retained exact draft includes that semicolon and builds. The syntax failure is historical context, not a current defect in head `675839b0...`.

## Why draft #304 stops at editability

The draft preserves a relative selected URL only through an editable-specific merge branch. Its lock serializer can repair generated metadata only when the selected distribution still carries a relative `VerbatimUrl`.

In the non-editable collision, URL selection can discard the relative spelling first. The serializer then sees an absolute selected distribution, excludes it from `relative_sources`, and has no evidence from which to recover the root project’s relative intent.

This demonstrates that resource identity, install mode, and presentation authority are separate properties.

## Generalized fork candidate

Fork-only draft `teamleaderleo/uv#37` tests one narrow policy after exact draft #304:

- for equivalent local directories, retain the relative spelling over the absolute spelling;
- merge editability independently so an editable declaration still wins;
- leave non-directory URLs unchanged.

Exact successful execution:

- tested head: `de93ecfc9e71af8ec15383beb287d320f38426ce`;
- generated merge: `56fb08842285b31145b61a0cc029618e12514269`;
- workflow run: `30969832800`;
- job: `92191555060`;
- artifact: `8916217206`;
- artifact ZIP SHA-256: `a631be2fb7773030e5e031b759e49e48f95c86973d528301e616890fd8f0ba97`.

The candidate produced zero absolute package-source records and zero absolute parent-metadata records across all eight editable, non-editable, order, and cache observations. All editable package sources remained editable.

The first execution attempt failed before compilation because the stored patch hunk declared 42 new lines while containing 39. The header was repaired without changing candidate logic.

## Why the passing candidate is not yet accepted

PR `astral-sh/uv#18176` intentionally established that explicit absolute path inputs must remain absolute. It includes a mixed relative-and-absolute lock snapshot and a dedicated absolute constraint-dependency test.

Meanwhile, `Manifest` retains separate project requirements and lookahead requirements, and `RequestedRequirements` carries a `direct` flag. `requirements_no_overrides` flattens those inputs before `Urls::from_manifest` merges equivalent resources. URL merging can inspect spelling and editability, but it no longer knows which spelling came from explicit root configuration, local-project source configuration, generated backend metadata, a constraint, or an override.

Therefore “relative always wins” may be only a fixture-passing heuristic. The stronger candidate invariant is:

> For equivalent resources, the higher-authority explicit declaration should determine serialized path intent, while install mode is merged independently.

The correct authority categories and precedence are not yet proven.

## Current negative control

Fork-only draft `teamleaderleo/uv#38` constructs this conflict:

- the root project explicitly declares `child` through an absolute path;
- a local parent declares the same `child` through a relative `tool.uv.sources` path;
- both root dependency orders are executed;
- package source and parent metadata are recorded separately.

A result that converts the root’s explicit absolute declaration to relative invalidates the spelling-only candidate and justifies an authority-aware merge model.

## Directions not worth pursuing yet

- **Blind serializer relativization:** cannot distinguish generated absolute metadata from intentional absolute input after origin is lost.
- **Metadata-only repair:** leaves the child package source absolute.
- **Poetry-version hunting:** a dependency-free backend reproduced the metadata shape, so Poetry is not required for the mechanism.
- **Async nondeterminism claims:** every executed order/cache matrix is invariant; a delayed multi-parent fixture is required.
- **Archives, symlinks, and `pylock.toml` first:** they are dominated by the unresolved ordinary-directory authority rule.
- **A competing upstream patch:** Astral already has an active draft, and upstream contact is not authorized.

## Adjacent but separate UV work

- `astral-sh/uv#16299` concerns local wheel paths exported to `pylock.toml` and needs an explicit export policy.
- `astral-sh/uv#19091` concerns rebasing transitive local paths in `uv pip compile`.
- `astral-sh/uv#18443` concerns parser and model support for relative local Git sources.

These share a portability theme but do not share the same demonstrated mechanism.

## Remaining probes

After the authority negative control:

1. decide whether URL collection needs an explicit authority-bearing wrapper;
2. add the non-editable sibling to the upstream-style regression fixture;
3. test constraints and overrides as competing authorities;
4. test symlink aliases where resource equality uses filesystem identity;
5. compare `uv.lock` and `pylock.toml` presentation behavior;
6. test existing-lock relocking, Windows drive/UNC paths, and local archives.

## External-contact state

No Astral issue, pull request, comment, review, reaction, email, or other upstream interaction has been created. All execution and repair candidates remain in the fork.
