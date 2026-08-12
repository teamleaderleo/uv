- Read CONTRIBUTING.md for guidelines on how to run tools
- ALWAYS ensure that new tests use the same style as existing tests for all parts of the test
- ALWAYS check whether the behavior of a new test is already covered by an existing test
- PREFER integration tests, e.g., at `it/...` over unit tests
- PREFER running specific tests over running the entire test suite
- PREFER `insta` snapshots following patterns in nearby tests over substring assertions
- When making changes for Windows from Unix, use `cargo xwin clippy` to check compilation
- NEVER perform builds with the release profile, unless asked or reproducing performance issues
- AVOID using `panic!`, `unreachable!`, `.unwrap()`, unsafe code, and clippy rule ignores
- PREFER patterns like `if let` to handle fallibility
- ALWAYS write `SAFETY` comments following our usual style when writing `unsafe` code
- PREFER `#[expect()]` over `[allow()]` if clippy must be disabled
- PREFER let chains (`if let` combined with `&&`) over nested `if let` statements
- NEVER update all dependencies in the lockfile and ALWAYS use `cargo update --precise` to make
  lockfile changes
- NEVER assume clippy warnings or test failures are pre-existing, it is very rare that `main` has
  warnings
- PREFER top-level imports over local imports or fully qualified names
- AVOID shortening variable names, e.g., use `version` instead of `ver`, and `requires_python`
  instead of `rp`
- PREFER [`TypeName`] references when writing Rust doc comments

## Owned-fork research guard

This fork is also used for Fieldwork research and candidate preparation.

- Automated workers ALWAYS use the literal `redirect.github.com` URL for every third-party GitHub issue, pull-request, or discussion reference they create.
- There are NO automated exceptions. This applies to pull-request bodies, issues, comments, reviews, tracked notes, drafts, experiment records, and commit messages.
- NEVER emit third-party `OWNER/REPOSITORY#NUMBER` shorthand or direct third-party issue, pull-request, or discussion URLs. If a direct reference is desired, a human must create it manually.
- Direct repository-root, source-file, documentation, release, and commit links are unaffected.
- Third-party upstream repositories are read-only to automated workers. Prepare patches, reproductions, tests, and human-facing text in owned surfaces; a human performs any upstream mutation manually.
- Branches intended for upstream submission SHOULD start from the relevant upstream revision or an upstream-equivalent base instead of fork `main`, so fork-only research instructions do not enter upstream diffs.
