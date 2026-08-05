# Fieldwork checkpoint — symlink alias boundary

Date: 2026-08-05  
State: source-supported hypothesis; execution deferred until path-authority policy is confirmed; upstream contact not authorized.

## Question considered

Could draft `astral-sh/uv-dev#304` preserve a relative selected package source but still leave generated parent metadata absolute when the two equivalent directory spellings reach the same resource through different symlink aliases?

## Source evidence

Directory resource equality in `crates/uv-resolver/src/resolver/urls.rs` accepts either:

1. exact `install_path` equality; or
2. `same_file::is_same_file` identity.

This means two distinct path spellings can be merged as one resource when one is a symlink alias of the other.

Path lowering constructs a `VerbatimUrl`, converts it to a file path, and stores that value as `install_path`. The ordinary directory path does not go through the explicit `simple_canonicalize` step used by Git path lowering. Therefore a symlink spelling can remain distinct in `install_path` while still matching another spelling through `is_same_file`.

Draft #304 later builds its metadata-repair set from exact `(package name, selected install_path)` pairs. `relative_metadata_requirement` repairs an absolute metadata URL only when the metadata requirement's exact install path appears in that set.

## Predicted failure mode

A credible alias fixture can produce this sequence:

1. root source: relative path through `../child-alias`;
2. generated parent metadata: absolute path through the real `../child` location;
3. URL collection: `is_same_file` recognizes both as the same directory and selects one source;
4. lock metadata repair: exact `install_path` lookup does not recognize alias and real path as equivalent;
5. child package source can be relative while parent `requires-dist` remains absolute.

This is not yet an executed finding. It is a source-supported mismatch between the equality relation used during URL selection and the equality relation used during metadata repair.

## Why it is deferred

The ordinary non-editable directory and authored-versus-generated authority rule are still under active validation. Running alias cases first would conflate two questions:

- which spelling has authority; and
- whether metadata repair uses the same resource-equivalence relation as URL selection.

The alias probe becomes discriminating only after the selected source policy is known.

## Smallest later probe

On Linux:

1. create real `child` and symlink `child-alias -> child`;
2. root explicitly selects `../child-alias` relatively;
3. a dependency-free parent backend emits the absolute real path for `child` in `Requires-Dist`;
4. run exact draft #304 and the accepted authority candidate;
5. inspect child package source and parent metadata separately;
6. reverse alias/real roles to rule out one-way normalization.

A repair should use the same resource identity relation for metadata correction as URL selection, or carry the selected resource identity directly rather than reconstructing it from an exact path pair.

## Not worth doing yet

- Windows junction/drive-letter variants: platform semantics would obscure the simpler Linux identity mismatch.
- changing `relative_sources` to canonical paths without a fixture: canonicalization could erase the user-authored alias spelling the lock is supposed to preserve.
- replacing all exact path comparisons with `is_same_file`: missing paths, archived sources, and cross-platform error behavior need explicit treatment.
