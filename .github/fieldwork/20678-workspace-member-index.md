# uv #20678 workspace member index authority discriminator

Exact source base: `79bbface771210df216b738e9bdc7df95e5a9e6b`.

This branch contains no product correction. It adds a deterministic local fixture for the workspace configuration-authority mismatch reported in `astral-sh/uv#20678`.

The discriminator:

1. Builds a minimal wheel using only Python's standard library.
2. Serves a populated PEP 503 index and a separate empty index on localhost.
3. Configures the workspace root to use only the empty index.
4. Runs `uv add --package child --index <populated-index> fieldwork-demo`.
5. Verifies that the populated index is written to the selected member while the workspace root is unchanged.
6. Removes the lockfile and uses a fresh cache for `uv lock`.
7. Expects the clean lock to fail because workspace index resolution does not consult the member-only index.

Run after building uv:

```console
cargo build --bin uv
bash .github/fieldwork/20678-workspace-member-index.sh
```

A correction is not selected yet. Plausible contracts include refusing to persist unusable member indexes, routing implicit workspace indexes to the workspace root, or requiring an explicit package source when a named index is intended to be member-specific.
