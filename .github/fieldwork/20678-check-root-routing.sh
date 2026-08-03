#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
patch_file="$repo_root/.github/fieldwork/20678-route-implicit-indexes-to-root.patch"

cd "$repo_root"
git diff --quiet
git diff --cached --quiet

git apply --check "$patch_file"
git apply "$patch_file"
trap 'git checkout -- crates/uv/src/commands/project/add.rs crates/uv/tests/project/edit.rs' EXIT

python3 - <<'PY'
from pathlib import Path

source = Path("crates/uv/src/commands/project/add.rs").read_text(encoding="utf-8")
start = source.index("    // Add any indexes that were provided on the command-line")
end = source.index("    // If `--frozen`, exit early", start)
body = source[start:end]

assert "workspace_index_content" in body
assert "index.is_none()" in body
assert "project.workspace().install_path() != project.root()" in body
assert "workspace_toml.add_index(index, workspace.install_path())" in body
assert "target.write(&content)" in body
assert "snapshot.revert()" in body

update_start = source.index("    // Update the project in memory", end)
update_end = source.index("    // Set the Ctrl-C handler", update_start)
update_body = source[update_start:update_end]
assert "VirtualProject::discover" in update_body
assert "target.update" in update_body
assert "snapshot.revert()" in update_body

print("implicit member indexes route to root; named source indexes stay local")
print("dual-file writes and rediscovery are covered by snapshot recovery")
PY

cargo fmt --check -- \
    crates/uv/src/commands/project/add.rs \
    crates/uv/tests/project/edit.rs
cargo test -p uv --test project \
    add_implicit_index_to_workspace_member_updates_root -- --nocapture
cargo test -p uv --test project \
    add_named_index_to_workspace_member_keeps_source_local -- --nocapture

printf '%s\n' 'uv #20678 workspace-root routing candidate applies and passes focused tests'
