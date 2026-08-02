# uv #20734: generate a stub-only package layout

Exact source base: `79bbface771210df216b738e9bdc7df95e5a9e6b`.

## Contract

A distribution named `<name>-stubs` is a PEP 561 stub-only distribution. Its importable stub tree uses a hyphenated directory such as `src/foo-stubs`, contains `.pyi` files, and does not provide a runtime package or console entry point.

Current `uv init --package foo-stubs` follows the ordinary packaged-application path. It writes a `[project.scripts]` entry and creates `src/foo_stubs/__init__.py`, while the uv build backend correctly looks for `src/foo-stubs/__init__.pyi`.

The staged candidate changes only initialization:

1. The default packaged-application kind is treated as a library when the distribution name ends in `-stubs`.
2. No `[project.scripts]` entry is generated.
3. `generate_package_scripts` creates `src/<normalized-stem>-stubs/__init__.pyi`.
4. It does not create `__init__.py` or `py.typed` for the stub-only package.
5. Ordinary package names continue through the existing path unchanged.

## Files

- `20734-generate-stub-only-layout.patch`: minimal source and focused-test candidate.
- `20734-check-candidate.sh`: applies the patch to the exact base, verifies the generated contract, formats, and runs the focused project test.

```console
bash .github/fieldwork/20734-check-candidate.sh
```

## Remaining gates

- Build the generated source distribution and wheel with the uv build backend.
- Inspect wheel paths and metadata to confirm PEP 561 layout.
- Add controls for explicit `--lib`, `--app`, and non-stubs names.
- Run the full project-init and build-backend suites.
- Rebase onto current upstream head and rerun exact gates.

This branch is internal and not submitted upstream.
