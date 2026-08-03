# uv #20678 workspace member index authority

Exact source base: `79bbface771210df216b738e9bdc7df95e5a9e6b`.

## TL;DR

`uv add --package child --index <url> ...` edits the selected member's `pyproject.toml`, so an unnamed or otherwise implicit index is persisted in a file that later workspace locking does not consult for general index resolution. A root project can reuse the same persisted index, and a single named index remains meaningful because `uv add` pins the new dependency to that index as a package source.

This branch contains no product correction. It now carries a three-case local matrix that separates the broken member-implicit case from those two valid controls.

## Source owner

In `crates/uv/src/commands/project/add.rs`:

1. `VirtualProject::discover_with_package` selects the requested member.
2. `PyProjectTomlMut` is created from `project.pyproject_toml().raw`, which is the selected member's file.
3. A single named CLI index is detected and passed into dependency edits, producing a `tool.uv.sources` pin.
4. All CLI indexes are later added through `toml.add_index(...)` to the same selected target.
5. `target.write(&content)` persists that member file.

The write is therefore internally consistent with the selected dependency target, but general workspace index authority belongs to the workspace root. The defect is not index parsing or one-shot resolution; it is persistence into a configuration scope that cannot replay the invocation.

## Deterministic matrix

The script uses only localhost and Python's standard library. It builds one minimal wheel, serves a populated PEP 503 index and a separate empty index, and exercises:

### Control A: root project plus implicit index

`uv add --index <populated> fieldwork-demo` writes the index to the root project. After removing the lockfile and using a fresh cache, `uv lock` should succeed because the persisted file is authoritative.

### Discriminator B: workspace member plus implicit index

`uv add --package child --index <populated> fieldwork-demo` writes the index to `child/pyproject.toml` while leaving the workspace root unchanged. After removing the lockfile and using a fresh cache, `uv lock` should fail because the root's empty default index remains the general workspace authority.

### Control C: workspace member plus one named index

`uv add --package child --index fieldwork-local=<populated> fieldwork-demo` writes the named index to the member and pins `fieldwork-demo` through `tool.uv.sources`. A clean workspace lock should succeed because this is an explicit package-source relationship, not an implicit workspace search index.

Run after building uv:

```console
cargo build --bin uv
bash .github/fieldwork/20678-workspace-member-index.sh
```

## Candidate contracts

### Route reusable implicit indexes to the workspace root

This best preserves the user's apparent request: the dependency remains in the selected member, while a general index is stored where later workspace operations can consult it. It requires careful two-file write, rollback, formatting, and Ctrl-C recovery semantics.

### Reject or warn instead of persisting a no-op

When the selected project is not the workspace root and the index is not converted into an explicit package source, `uv add` could refuse the unusable persistence or complete the one-shot resolution with a clear warning and no saved member index. This is simpler but makes the command less self-contained.

### Make member indexes general workspace inputs

This would broaden workspace configuration semantics and raises ordering, conflict, security, and discoverability questions across members. It should not be selected as a small bug fix without explicit design agreement.

## Promotion threshold

Select a correction only after a native integration test reproduces all three cases and the dual-file rollback owner is mapped. The preferred first implementation probe is root routing, but it loses if current snapshot/revert machinery cannot safely restore both files or if existing workspace policy intentionally forbids command-driven root mutation from a selected member.

## Remaining gates

1. Port the matrix into `crates/uv/tests/project/edit.rs` using existing integration-test and snapshot patterns.
2. Map `AddTarget::snapshot`, `write`, and Ctrl-C restoration for a dependency edit in the member plus an index edit in the root.
3. Test index ordering when the root already contains named, explicit, and default indexes.
4. Test credentials are not persisted and relative path indexes are resolved against the file that owns them.
5. Recheck current issue and PR overlap immediately before selecting a product branch.

No upstream contact is authorized.
