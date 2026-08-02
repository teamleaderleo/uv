#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
patch_file="$repo_root/.github/fieldwork/20734-generate-stub-only-layout.patch"

cd "$repo_root"
git diff --quiet
git diff --cached --quiet

git apply --check "$patch_file"
git apply "$patch_file"
trap 'git checkout -- crates/uv/src/commands/project/init.rs crates/uv/tests/project/init.rs' EXIT

python3 - <<'PY'
from pathlib import Path

source = Path("crates/uv/src/commands/project/init.rs").read_text(encoding="utf-8")

kind_start = source.index("impl InitProjectKind {")
kind_end = source.index("\n#[derive(Debug)]\nenum Author", kind_start)
kind_body = source[kind_start:kind_end]
assert 'name.as_str().ends_with("-stubs")' in kind_body
assert "Self::ApplicationWithLibrary" in kind_body
assert "Self::Library" in kind_body

scripts_start = source.index("fn generate_package_scripts(")
scripts_end = source.index("\n#[derive(Debug, Clone)]\nenum GitDiscoveryResult", scripts_start)
scripts_body = source[scripts_start:scripts_end]
assert 'strip_suffix("-stubs")' in scripts_body
assert 'format!("{module_name}-stubs")' in scripts_body
assert 'pkg_dir.join("__init__.pyi")' in scripts_body
assert scripts_body.index('pkg_dir.join("__init__.pyi")') < scripts_body.index('pkg_dir.join("__init__.py")')

print("stub-only init contract: library project, hyphenated PEP 561 package, __init__.pyi")
PY

cargo fmt --check -- crates/uv/src/commands/project/init.rs crates/uv/tests/project/init.rs
cargo test -p uv --test project init_stubs_package -- --nocapture

printf '%s\n' 'uv #20734 stub-only initializer candidate applies and passes focused test'
