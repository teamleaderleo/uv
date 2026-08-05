# Fieldwork checkpoint — `pylock.toml` provenance boundary

Date: 2026-08-05  
State: source analysis; directory behavior is downstream of URL selection, while archive policy remains separate; upstream contact not authorized.

## Question considered

Does the local-directory provenance repair need an independent `pylock.toml` implementation, or is that output downstream of the same selected URL and `uv.lock` source spelling?

## Two export paths

`PylockToml::from_resolution` serializes directly from `ResolverOutput`. For local directories it calls `try_relative_to_if` using:

```text
!dist.url.was_given_absolute()
```

Therefore direct resolution-to-pylock export inherits the exact `VerbatimUrl` selected by URL collection. If equivalent-resource merging discards root path intent, `from_resolution` repeats that loss. A correct root-versus-lookahead selection policy can repair this path without a pylock-specific authority model.

`PylockToml::from_lock` instead reconstructs a distribution from the existing `uv.lock` package and uses the source URL's stored `given()` spelling when available. Therefore lock-to-pylock export inherits whatever source spelling the lock serializer preserved.

## Consequence

For local **directory package sources**, pylock behavior is not an independent first repair lane:

1. direct export follows resolver URL selection;
2. export from a lock follows the serialized lock source;
3. neither path can recover path authority after the selected URL or lock source has already lost it.

This supports fixing provenance at URL collection and lock serialization before adding a pylock-specific workaround.

## Important scope limit

Public issue `astral-sh/uv#16299` concerns local wheel/archive files in pylock output. Those are serialized through archive/path branches and have separate questions about portability, hashes, and whether an explicitly absolute artifact path should remain absolute.

That issue should not be presented as evidence that the directory repair must relativize all pylock paths. It is an adjacent export-policy problem.

## What pylock does not prove for this issue

The current pylock package conversion does not reproduce the parent package's lockfile `requires-dist` metadata spelling as an equivalent field in this probe. A pylock directory-source test can verify the selected child source path, but it is not a substitute for the `uv.lock` assertion that generated parent metadata was repaired.

## Smallest later probe

After the root-versus-lookahead candidate has a result:

1. export pylock directly from the same resolution fixture;
2. export pylock from the resulting `uv.lock`;
3. compare the child `packages.directory.path` spelling;
4. repeat the explicit-absolute-root negative control;
5. keep local wheel/archive cases in a separate matrix tied to issue #16299.

## Directions declined

- adding pylock-only relativization now: too late to recover discarded authority and risks changing intentional absolute input;
- combining directory and wheel/archive tests: they use different source types and policy constraints;
- treating a relative pylock child path as proof that parent lock metadata is fixed: pylock does not expose the same metadata representation.
