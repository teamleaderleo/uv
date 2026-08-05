# Fieldwork checkpoint — requirement authority is erased before URL merge

Date: 2026-08-05  
State: source finding sharpened; root-versus-lookahead behavioral control running; upstream contact not authorized.

## Question considered

Is “prefer the relative spelling for equivalent local directories” the underlying rule, or is it only a proxy for a stronger rule such as “prefer root configuration over lookahead metadata”?

## Source evidence

`Manifest` keeps inputs in distinct structures:

- `requirements` contains root project requirements;
- `lookaheads` contains requirements discovered from local or otherwise inspected distributions;
- each `RequestedRequirements` carries a `direct` boolean;
- `Manifest::user_requirements` already filters lookaheads by that direct flag for another resolver policy.

`requirements_no_overrides` emits lookahead requirements before project requirements and constraints, then `Urls::from_manifest` merges equivalent resources from that flat iterator. Its stored value is only `VerbatimParsedUrl`, so the surviving URL carries resource identity, editability, and serialized spelling together.

## An existing root-context signal is available

A new authority type may not be required for the first repair.

Both `uv_pep508::Requirement` and `uv_distribution_types::Requirement` already carry `origin: Option<RequirementOrigin>`. The latter preserves that origin through conversion to and from parsed URL requirements. `RequirementOrigin` distinguishes file, project, group, and workspace inputs.

Project locking explicitly marks lowered root/workspace requirements with `RequirementOrigin::Workspace`. Requirements read from explicitly supplied source-tree input can similarly receive `RequirementOrigin::Project`.

The ordinary resolver lookahead path is different:

1. built `METADATA` is parsed into `Requirement` values without assigning a root/file origin;
2. `RequiresDist::from_project_workspace` may apply a transitive project's `tool.uv.sources`, but it preserves the parsed requirement's public origin rather than assigning a new one for that source-table entry;
3. `LookaheadResolver::lookahead` takes the lowered `metadata.requires_dist`, adjusts only recursive self-references, and places those requirements directly into `RequestedRequirements`;
4. `Manifest` flattens those lookahead values ahead of root requirements;
5. `Urls::from_manifest` discards `requirement.origin` when it extracts only the parsed URL.

Therefore `origin.is_some()` is a reliable first discriminator for root/file-context input versus ordinary lookahead in the reported collision. It is **not** a complete authored-versus-generated signal: a transitive local project's explicit `tool.uv.sources` can still reach URL collection with `origin = None`.

## Important limit of `direct`

`RequestedRequirements::direct` is not equivalent to root authority. Lookahead marks dependencies “direct” whenever the originating distribution is a local source directory. That can include dependencies of a local parent and does not identify how a particular child URL spelling was authored.

The per-requirement `origin` is the narrower and more relevant first discriminator, but neither field alone represents a complete first-party source hierarchy.

## Explicit absolute intent is a compatibility requirement

PR `astral-sh/uv#18176` makes intentional absolute input a hard compatibility constraint for this research. Its `lock_relative_and_absolute_paths` snapshot keeps one local dependency relative while changing a sibling declared by an absolute path to an absolute lockfile source and absolute `requires-dist` entry. The same PR adds a dedicated absolute constraint-dependency test whose stated requirement is that the user-provided absolute path remain absolute.

Therefore “make local paths portable whenever possible” is not the accepted upstream policy. UV is expected to preserve the root author’s explicit absolute-versus-relative choice.

## Interpretation

The resolver currently merges three independent properties through one replaceable URL object:

1. resource identity — whether two URLs designate the same directory;
2. install mode — editable or non-editable;
3. presentation authority — which spelling should be serialized and why.

Draft #304 separates editability from replacement for the reported editable collision. The executed non-editable failure shows that presentation authority remains coupled to whichever URL survives.

The completed fork experiment “relative wins, editability is merged independently” fixed all eight issue observations, but it is rejected as a final policy. Because lookahead metadata is emitted first, a generated relative spelling can be retained over an explicitly absolute root declaration.

A defensible narrow first policy is:

> When equivalent URLs disagree, root/file-context spelling outranks origin-free lookahead spelling; editability is merged independently.

This does not resolve competing lookahead projects or two explicit root/file origins.

## Negative-control repair

The first authority fixture used a Hatchling parent with a nested `[tool.uv.sources]` table. That was rejected before execution because nested source configuration is not proof that built metadata carries a relative direct URL; the control could have passed without creating the intended conflict.

The replacement fixture uses a dependency-free PEP 517 backend whose generated metadata contains the exact line:

```text
Requires-Dist: child @ file:../child
```

The harness calls the backend before locking and fails unless that exact relative metadata requirement exists. The root independently declares the same child through an absolute path. It also fails if the final lock lacks a local path in either the child source or parent metadata, preventing a vacuous pass.

The flawed carrier `teamleaderleo/uv#38` was closed before execution. The corrected control now runs with the root-context candidate in fork-only draft `teamleaderleo/uv#40`.

## Active root-context candidate

The candidate applies after exact draft #304 and changes only URL collection behavior:

1. retain `origin.is_some()` beside each parsed URL during collection;
2. for equivalent local directories, prefer root/file-context spelling over origin-free lookahead spelling;
3. merge editability independently;
4. retain draft #304 behavior when both candidates have equal authority;
5. drop the sidecar before the existing override and downstream interfaces.

This deliberately tests only the reported root-versus-lookahead boundary.

## Directions considered

### Add a general provenance enum immediately

Deferred. `RequirementOrigin` already preserves the exact root-context distinction needed by the reported collision. A broader authority model should be introduced only if executed conflicts show the existing signal is insufficient.

### Use `RequestedRequirements::direct` as the complete authority signal

Rejected. It classifies the local parent distribution, not the individual child requirement's source authority.

### Keep universal relative precedence

Rejected as final policy. It passed the reported matrix but can override intentional absolute root input due to lookahead-first ordering.

### Infer authority during lock serialization

Rejected as the primary repair. Once URL collection has discarded the losing URL and origin, serialization cannot distinguish explicit root intent from lookahead metadata.

### Describe `origin.is_some()` as all authored input

Rejected after tracing distribution lowering. A transitive project source table can alter a requirement while its public origin remains unset. The candidate and notes now use the narrower “root/file context versus lookahead” wording.

### Treat root/file context as a complete final hierarchy

Not accepted. It does not order two root/file origins, two transitive projects, constraints, groups, or workspace members against each other. Overrides remain on a separate replacement path.

## Current implementation discriminator

Fork PR `teamleaderleo/uv#40` runs two suites against exact draft #304 plus the root-context sidecar:

1. the unchanged eight-observation issue matrix, which must keep every editable and non-editable relative root declaration relative;
2. the metadata-exact authority control, whose child package source must keep the root's explicit absolute declaration in both dependency orders.

A successful result would establish that existing `RequirementOrigin` is sufficient for the reported root-versus-lookahead repair boundary. It would not establish a complete first-party source hierarchy.

## Not yet considered

- two origin-free lookahead projects with conflicting path intent;
- two explicit origins with conflicting absolute-versus-relative intent;
- constraints and groups as competing URL authorities;
- marker-separated forks where each spelling is valid in a different environment;
- existing-lock preferences reintroducing a spelling after provenance metadata has been serialized away;
- environment-expanded paths, for which `was_given_absolute()` intentionally returns false;
- whether every metadata acquisition path preserves the same root-versus-lookahead origin distinction.
