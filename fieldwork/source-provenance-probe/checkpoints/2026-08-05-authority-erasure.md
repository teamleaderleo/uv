# Fieldwork checkpoint — requirement authority is erased before URL merge

Date: 2026-08-05  
State: source finding sharpened; origin-aware behavioral control running; upstream contact not authorized.

## Question considered

Is “prefer the relative spelling for equivalent local directories” the underlying rule, or is it only a proxy for a stronger rule such as “prefer explicit project configuration over generated transitive metadata”?

## Source evidence

`Manifest` keeps inputs in distinct structures:

- `requirements` contains direct project requirements;
- `lookaheads` contains requirements discovered from local or otherwise inspected distributions;
- each `RequestedRequirements` carries a `direct` boolean;
- `Manifest::user_requirements` already filters lookaheads by that direct flag for another resolver policy.

`requirements_no_overrides` emits lookahead requirements before project requirements and constraints, then `Urls::from_manifest` merges equivalent resources from that flat iterator. Its stored value is only `VerbatimParsedUrl`, so the surviving URL carries resource identity, editability, and serialized spelling together.

## An existing origin signal is available

A new authority type may not be required for the first repair.

Both `uv_pep508::Requirement` and `uv_distribution_types::Requirement` already carry `origin: Option<RequirementOrigin>`. The latter preserves that origin through conversion to and from parsed URL requirements. `RequirementOrigin` distinguishes file, project, group, and workspace inputs.

Project locking explicitly marks lowered workspace requirements with `RequirementOrigin::Workspace`. Source-tree resolution similarly assigns `RequirementOrigin::Project` to requirements extracted from an explicitly supplied local project.

The ordinary lookahead path is different and confirms the candidate distinction more directly:

1. built `METADATA` is parsed into `Requirement` values without assigning an authored origin;
2. `LookaheadResolver::lookahead` takes `metadata.requires_dist`, adjusts only recursive self-references, and places those requirements directly into `RequestedRequirements`;
3. `Manifest` later flattens those values ahead of root requirements;
4. `Urls::from_manifest` discards `requirement.origin` when it extracts only the parsed URL.

Therefore the collision in issue #20477 is expected to contain an origin-free generated requirement and an authored root requirement. The origin signal survives until URL collection, where it is currently discarded.

## Important limit of `direct`

`RequestedRequirements::direct` is not equivalent to root authority. Lookahead marks dependencies “direct” whenever the originating distribution is a local source directory. That can include dependencies of a local parent and does not identify whether a particular child URL spelling came from root configuration or generated metadata.

The existing per-requirement `origin` is therefore a more relevant first discriminator than the parent-level `direct` boolean.

## Explicit absolute intent is a compatibility requirement

PR `astral-sh/uv#18176` makes intentional absolute input a hard compatibility constraint for this research. Its `lock_relative_and_absolute_paths` snapshot keeps one local dependency relative while changing a sibling declared by an absolute path to an absolute lockfile source and absolute `requires-dist` entry. The same PR adds a dedicated absolute constraint-dependency test whose stated requirement is that the user-provided absolute path remain absolute.

Therefore “make local paths portable whenever possible” is not the accepted upstream policy. UV is expected to preserve the author’s explicit absolute-versus-relative choice.

## Interpretation

The resolver currently merges three independent properties through one replaceable URL object:

1. resource identity — whether two URLs designate the same directory;
2. install mode — editable or non-editable;
3. presentation authority — which spelling should be serialized and why.

Draft #304 separates editability from replacement for the reported editable collision. The executed non-editable failure shows that presentation authority remains coupled to whichever URL survives.

The completed fork experiment “relative wins, editability is merged independently” fixed all eight issue observations, but it is rejected as a final policy. Because lookahead metadata is emitted first, generated relative metadata can be retained over an explicitly absolute root declaration.

A more defensible narrow policy is:

> When equivalent URLs disagree, a requirement with an explicit origin outranks origin-free generated metadata; editability is merged independently.

That still leaves conflicts between two explicit origins unresolved.

## Negative-control repair

The first authority fixture used a Hatchling parent with a nested `[tool.uv.sources]` table. That was rejected before execution because nested source configuration is not proof that built metadata carries a relative direct URL; the control could have passed without creating the intended conflict.

The replacement fixture uses a dependency-free PEP 517 backend whose generated metadata contains the exact line:

```text
Requires-Dist: child @ file:../child
```

The harness calls the backend before locking and fails unless that exact relative metadata requirement exists. The root independently declares the same child through an absolute path. It also fails if the final lock lacks a local path in either the child source or parent metadata, preventing a vacuous pass.

The flawed carrier `teamleaderleo/uv#38` was closed before execution. The corrected control now runs with the origin-aware candidate in fork-only draft `teamleaderleo/uv#40`.

## Active origin-aware candidate

The candidate applies after exact draft #304 and changes only URL collection behavior:

1. retain `origin.is_some()` beside each parsed URL during collection;
2. for equivalent local directories, prefer authored spelling over origin-free generated metadata;
3. merge editability independently;
4. retain draft #304 behavior when both candidates have equal authority;
5. drop the sidecar before the existing override and downstream interfaces.

This deliberately tests only authored input versus generated metadata. It does not claim a complete hierarchy among workspace, project, group, file, constraint, and override origins.

## Directions considered

### Add a general provenance enum immediately

Deferred. `RequirementOrigin` already preserves the exact first distinction needed by the reported collision. A broader authority enum should be introduced only if executed conflicts show the existing signal is insufficient.

### Use `RequestedRequirements::direct` as the complete authority signal

Rejected. It classifies the local parent distribution, not the individual child requirement’s authorship.

### Keep universal relative precedence

Rejected as final policy. It passed the reported matrix but can override intentional absolute root input due to lookahead-first ordering.

### Infer authority during lock serialization

Rejected as the primary repair. Once URL collection has discarded the losing URL and origin, serialization cannot distinguish explicit absolute intent from generated absolute metadata.

### Treat `origin.is_some()` as a complete final hierarchy

Not accepted. It distinguishes authored input from origin-free metadata, but does not order workspace, project, group, file, constraint, and override origins against each other. Overrides already have separate resolver semantics; equal-authority conflicts still require tests.

## Current implementation discriminator

Fork PR `teamleaderleo/uv#40` runs two suites against exact draft #304 plus the origin-aware sidecar:

1. the unchanged eight-observation issue matrix, which must keep every editable and non-editable relative root declaration relative;
2. the metadata-exact authority control, whose child package source must keep the root’s explicit absolute declaration in both dependency orders.

A successful result would establish that existing `RequirementOrigin` is sufficient for the first repair boundary. It would not establish precedence among two authored declarations.

## Not yet considered

- two explicit origins with conflicting absolute-versus-relative intent;
- constraints and overrides as competing URL authorities;
- marker-separated forks where each spelling is valid in a different environment;
- existing-lock preferences reintroducing a spelling after provenance metadata has been serialized away;
- environment-expanded paths, for which `was_given_absolute()` intentionally returns false;
- whether requirements reconstructed from every build-backend path consistently remain origin-free.
