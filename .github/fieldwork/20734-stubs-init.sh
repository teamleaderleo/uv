#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
uv_bin="$repo_root/target/debug/uv"
work_dir="${RUNNER_TEMP:-/tmp}/fieldwork-uv-20734"
project_dir="$work_dir/foo-stubs"

rm -rf "$work_dir"
mkdir -p "$work_dir"
trap 'rm -rf "$work_dir"' EXIT

"$uv_bin" init --package "$project_dir"

printf '%s\n' '--- generated files ---'
find "$project_dir" -maxdepth 4 -type f -print | LC_ALL=C sort
printf '%s\n' '--- pyproject.toml ---'
cat "$project_dir/pyproject.toml"

test -f "$project_dir/src/foo_stubs/__init__.py"
test ! -e "$project_dir/src/foo-stubs/__init__.pyi"

set +e
(
  cd "$project_dir"
  "$uv_bin" build
) >"$work_dir/build.stdout" 2>"$work_dir/build.stderr"
build_status=$?
set -e

printf '%s\n' '--- build stdout ---'
cat "$work_dir/build.stdout"
printf '%s\n' '--- build stderr ---'
cat "$work_dir/build.stderr"
printf 'build_status=%s\n' "$build_status"

test "$build_status" -ne 0
grep -F 'Expected a Python module at: src/foo-stubs/__init__.pyi' "$work_dir/build.stderr"

printf '%s\n' 'current mismatch reproduced'
