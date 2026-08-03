# UV stubs-package backend boundary review

State: `ACTIVE OVERLAP REVIEW — NO COMPETING SOURCE PATCH`

Canonical issues: `astral-sh/uv#19663`, `astral-sh/uv#20734`  
Active canonical implementation: `astral-sh/uv#19671`  
Exact implementation head: `082af3c5eb95bbc0f0173ebc67965919c14e1a0a`  
Exact base: `3d00ce70244d8b5660e8c02136568a9147dc97e8`

## Confirmed baseline defect

Controlled run `30759500353` at the current controlled fork reproduced the default `uv_build` mismatch:

```text
uv init --package foo-stubs
  creates src/foo_stubs/__init__.py
uv build
  expects src/foo-stubs/__init__.pyi
  exits 2
```

The generated project also contains a `[project.scripts]` entry targeting `foo_stubs:main`, which is inappropriate for a type-only stub distribution.

## Active patch review

PR #19671 changes initialization to:

- suppress the console script for names recognized as stub distributions;
- use `src/foo-stubs` instead of `src/foo_stubs`;
- create `__init__.pyi` and return early when the selected backend is `uv_build`.

The first two decisions are applied to every build backend, while the stub-only file generation and early return are limited to `uv_build`.

That creates a backend boundary requiring execution:

- Hatch, Flit, PDM, Poetry, and setuptools receive `src/foo-stubs/__init__.py`, a hyphenated directory that is not the ordinary import package `foo_stubs`.
- Maturin and Scikit receive the same hyphenated directory, but generated Python code imports `foo_stubs._core`.
- console scripts are suppressed for every backend.

This does not establish that those builds fail; some backends may silently produce empty or otherwise surprising distributions. The distinction must be executed rather than inferred.

## Controlled matrix

The workflow compares exact base and exact PR head across:

```text
uv
hatch
flit
pdm
poetry
setuptools
maturin
scikit
```

For each source/backend pair it retains:

- init status and generated tree;
- `pyproject.toml`;
- hyphenated and underscored module markers;
- console-script presence;
- build status, stdout, stderr, and produced distribution names.

The matrix is review evidence only. It does not create a competing source patch or communicate with canonical upstream.

## Selection boundary

A safe patch should make the stub-only special case explicit per backend. At minimum it must not rewrite third-party-backend package directories to a hyphenated path while continuing to generate runtime `__init__.py` or imports using `foo_stubs`.

No canonical issue comment, pull request, review, reaction, or maintainer contact is authorized or made.
