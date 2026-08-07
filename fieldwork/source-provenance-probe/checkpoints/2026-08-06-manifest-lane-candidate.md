# Fieldwork checkpoint — manifest-lane authority candidate

Date: 2026-08-06  
State: execution candidate; no result claimed; upstream contact not authorized.

## Rejected predecessor

The `RequirementOrigin` candidate built and completed the original eight-observation matrix, but all four non-editable package-source and parent-metadata paths remained absolute. `origin.is_some()` is therefore not a usable authority discriminator for this resolver path.

Its custom Core Metadata negative control was also invalid: `Requires-Dist: child @ file:../child` cannot be parsed without a working directory.

## Candidate boundary

`Manifest::requirements_no_overrides` still knows which iterator lane produced each requirement before flattening them into one stream:

1. lookahead requirements;
2. root or workspace requirements;
3. user constraints.

The candidate adds a private iterator variant that returns each requirement with one boolean: `root_context`.

- lookahead requirements receive `false`;
- root or workspace requirements receive `true`;
- user constraints receive `true`;
- overrides remain on their existing separate path.

`Urls::from_manifest` retains that bit only while selecting among equivalent URLs.

For equivalent local directories:

- root-context spelling outranks lookahead spelling;
- equal-context pairs retain draft #304's current replacement and editable behavior;
- editability is merged independently;
- non-directory URL replacement remains unchanged.

The sidecar is removed before the existing `Urls` interfaces.

## Required evidence

### Original issue matrix

The unchanged editable and non-editable matrix must produce:

- relative package sources in all eight observations;
- relative parent metadata in all eight observations;
- editable package sources still marked editable;
- dependency-order and cold/warm invariance.

### Valid reverse-direction control

The root declares `child` through an explicit absolute path. A local `parent` project declares `child` through relative `[tool.uv.sources]` and a normal PEP 621 dependency.

This is a valid relative source context because UV lowers the local project's source table with the project directory available. The final lock must show both facts:

- child package source remains absolute, proving root presentation won;
- parent metadata remains relative, proving the lower-authority relative project source existed;
- both dependency orders produce the same result.

## Explicit limits

This candidate does not establish precedence among:

- root requirements and user constraints;
- two lookahead projects;
- two workspace members;
- group-scoped and ordinary root requirements;
- existing-lock preferences;
- marker-separated forks.

It also does not address symlink aliases, archives, Windows path forms, or `pylock.toml` independently.

## Implementation carrier

Branch: `research/manifest-lane-uv-dev-304-20260806`.

The workflow applies exact draft `uv-dev#304@675839b0b1b1c66ee3b02139e1237094722ec2b2`, runs the exact-anchor candidate transform, fences the resulting production and test diff, checks Rust formatting, builds UV, executes both suites, and retains the exact patch and transcripts.
