# uv #20678: route reusable member indexes to the workspace root

Exact source base: `79bbface771210df216b738e9bdc7df95e5a9e6b`.

State: `CANDIDATE STAGED — UNEXECUTED`.

## Contract

When `uv add --package <member>` receives command-line indexes:

- a single named index remains in the selected member because the newly added dependency is pinned to it through `tool.uv.sources`;
- unnamed indexes and multi-index search configuration are persisted in the workspace root, because later workspace operations consult the root for general index authority;
- dependency edits remain in the selected member.

This preserves the meaningful package-source case without persisting general search configuration into a member file that cannot replay it.

## Source correction

The staged patch changes `crates/uv/src/commands/project/add.rs`:

1. It builds a second `PyProjectTomlMut` only when the selected project is a workspace member and the indexes are not represented by one named package-source pin.
2. Relative path indexes are resolved against the workspace root that will own them.
3. The member and root writes are treated as one operation; an error restores the existing `AddTargetSnapshot`, which already contains both TOML files and the lockfile.
4. A root edit triggers full `VirtualProject::discover` rather than member-only `update_member`, preventing stale in-memory workspace configuration.
5. Rediscovery failure also restores the snapshot.

## Focused controls

The test patch adds two `--frozen` integration tests so no external index access is required:

- an unnamed index supplied while targeting `child` appears in the root while the dependency appears in `child/pyproject.toml`;
- one named index stays in the member and creates the expected `tool.uv.sources` pin, while the root remains unchanged.

The separate research branch `research/uv-20678-workspace-member-index-authority` contains the localhost replay matrix. Its expected behavior is:

- root-owned implicit index: clean lock succeeds;
- member-owned implicit index on current source: clean lock fails;
- member-owned single named source index: clean lock succeeds.

## Files

- `20678-route-implicit-indexes-to-root.patch`: product and integration-test candidate.
- `20678-check-root-routing.sh`: clean-tree apply, structural checks, formatting, and focused tests.

```console
bash .github/fieldwork/20678-check-root-routing.sh
```

## Remaining gates

1. Execute the harness in a clean checkout at the exact base.
2. Run the localhost replay matrix against the applied candidate and reverse its discriminator B expectation from failure to success.
3. Add rollback tests for a failed lock after both TOML files change.
4. Test existing root index ordering, multi-index input, default indexes, explicit indexes, relative path indexes, and credential redaction.
5. Run the complete project edit, lock, and sync suites plus formatting and clippy gates.
6. Refresh the upstream issue, comments, and adjacent PR search immediately before any authorization request.

## Evidence boundary

The patch and tests are staged from exact source review. They have not run in this environment because a clean repository checkout is unavailable locally and existing connected Actions remain queued. No passing result is claimed.

No upstream contact is authorized.
