# Fieldwork checkpoint — adjacent path issue triage

Date: 2026-08-05  
State: scope review; no upstream contact authorized.

## Purpose

Check whether other open UV path-portability reports duplicate, supersede, or materially widen the local-directory provenance finding before spending work on additional serializers or source types.

## Issues reviewed

### `astral-sh/uv#20477` — relative `tool.uv.sources` paths become absolute in `uv.lock`

This remains the direct owner of the confirmed regression. Its active implementation is private draft `astral-sh/uv-dev#304`. The exact draft fixes editable directories but not the executed non-editable sibling.

**Decision:** continue fork-only validation and repair research here. Do not open a competing upstream implementation.

### `astral-sh/uv#16299` — relative local files when exporting `pylock.toml`

This requests relative paths for local wheel files emitted by `uv export`. The issue explicitly notes that changing absolute paths may break expected use cases and leaves open whether relative output should be opt-in or standard behavior.

**Why it matters:** it confirms that `pylock.toml` portability is an active concern and that absolute-versus-relative presentation has policy consequences.

**Why it is not the current repair lane:** it concerns exported local wheel/index files, not equivalent local-directory requirements merged during resolution. It also needs an explicit policy decision about intentionally absolute inputs. A passing `uv.lock` directory patch cannot be assumed to define the correct `pylock.toml` behavior.

**Decision:** retain as a later serializer-policy comparison, not evidence that draft #304 should modify `pylock.toml` now.

### `astral-sh/uv#19091` — `uv pip compile` loses the relative structure of transitive local dependencies

This report describes paths that remain relative to a dependency project rather than being rebased to the compiled output project's directory.

**Why it is related:** both failures make generated dependency records non-portable or incorrect when project roots differ.

**Why it is distinct:** this is an output-root rebasing problem in `uv pip compile`, not a same-resource URL-selection collision in `uv lock`. Its expected transformation is “rebase relative to another output root,” while the current finding is “do not discard explicit relative provenance when an equivalent absolute spelling appears.”

**Decision:** do not combine implementations or claims. Revisit only if a shared provenance abstraction emerges after the lock repair is understood.

### `astral-sh/uv#18443` — relative paths in local Git sources

This requests support for relative `file://` Git sources to combine revision pinning, offline use, and portability.

**Why it is distinct:** Git source identity includes repository and revision semantics, and relative local Git URLs are currently rejected at parsing/configuration time. The confirmed directory regression happens after both spellings have already parsed and been judged the same resource.

**Decision:** not worth entering from this fieldwork lane. It would widen both parser and source-type scope without testing the current repair.

## Scope conclusion

The current high-value lane remains local directory selection and lock serialization. Adjacent reports show a broader product theme—portable local-source presentation—but they divide into different mechanisms:

1. equivalent-resource provenance loss in `uv lock`;
2. output-root rebasing in `uv pip compile`;
3. export policy for local wheel files in `pylock.toml`;
4. parser/model support for relative local Git sources.

Treating them as one bug would produce a vague abstraction without evidence. The useful common question is narrower: where should UV preserve, rebase, reject, or canonicalize user-provided path provenance for each output format and source type?

## Deferred questions

- Does `pylock.toml` export of a resolved relative directory use the selected `VerbatimUrl` or reconstruct from an absolute install path?
- Can the pip-compile rebasing issue reuse a provenance type without coupling command-specific output roots?
- Should conflicting explicit relative and absolute declarations be rejected rather than resolved by precedence?

These remain deferred until the generalized local-directory candidate has an exact execution result.
