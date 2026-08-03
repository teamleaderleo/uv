#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
uv_bin="$repo_root/target/debug/uv"
work_dir="${RUNNER_TEMP:-/tmp}/fieldwork-uv-20678"
index_root="$work_dir/index"
port_file="$work_dir/http-port"
server_log="$work_dir/http.log"

rm -rf "$work_dir"
mkdir -p "$index_root/simple/fieldwork-demo" "$index_root/empty" "$index_root/files"

server_pid=
cleanup() {
    if [[ -n "${server_pid:-}" ]]; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    rm -rf "$work_dir"
}
trap cleanup EXIT

python3 - "$index_root/files/fieldwork_demo-1.0.0-py3-none-any.whl" <<'PY'
import csv
import io
import sys
import zipfile

wheel_path = sys.argv[1]
files = {
    "fieldwork_demo/__init__.py": "__version__ = '1.0.0'\n",
    "fieldwork_demo-1.0.0.dist-info/METADATA": (
        "Metadata-Version: 2.1\n"
        "Name: fieldwork-demo\n"
        "Version: 1.0.0\n"
    ),
    "fieldwork_demo-1.0.0.dist-info/WHEEL": (
        "Wheel-Version: 1.0\n"
        "Generator: linux-fieldwork\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ),
}
record = io.StringIO()
writer = csv.writer(record, lineterminator="\n")
for path in files:
    writer.writerow([path, "", ""])
writer.writerow(["fieldwork_demo-1.0.0.dist-info/RECORD", "", ""])
files["fieldwork_demo-1.0.0.dist-info/RECORD"] = record.getvalue()

with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
    for path, content in files.items():
        wheel.writestr(path, content)
PY

cat >"$index_root/simple/fieldwork-demo/index.html" <<'HTML'
<!doctype html>
<a href="../../files/fieldwork_demo-1.0.0-py3-none-any.whl">fieldwork_demo-1.0.0-py3-none-any.whl</a>
HTML

python3 - "$index_root" "$port_file" >"$server_log" 2>&1 <<'PY' &
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

root = sys.argv[1]
port_file = Path(sys.argv[2])
handler = partial(SimpleHTTPRequestHandler, directory=root)
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
port_file.write_text(str(server.server_port), encoding="utf-8")
server.serve_forever()
PY
server_pid=$!

for _ in $(seq 1 100); do
    [[ -s "$port_file" ]] && break
    sleep 0.05
done
[[ -s "$port_file" ]]
port=$(cat "$port_file")
base_url="http://127.0.0.1:$port"
populated_index="$base_url/simple"
empty_index="$base_url/empty"

write_project() {
    local project_dir=$1
    local project_name=$2
    mkdir -p "$project_dir/src/${project_name//-/_}"
    cat >"$project_dir/pyproject.toml" <<EOF
[project]
name = "$project_name"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["uv_build>=0.8.0,<0.9.0"]
build-backend = "uv_build"
EOF
    printf '%s\n' '__version__ = "0.1.0"' \
        >"$project_dir/src/${project_name//-/_}/__init__.py"
}

write_workspace() {
    local workspace=$1
    mkdir -p "$workspace/child"
    cat >"$workspace/pyproject.toml" <<EOF
[tool.uv.workspace]
members = ["child"]

[[tool.uv.index]]
name = "empty-root"
url = "$empty_index"
default = true
EOF
    write_project "$workspace/child" child
}

run_clean_lock() {
    local project_dir=$1
    local cache_name=$2
    local stdout=$3
    local stderr=$4
    rm -f "$project_dir/uv.lock"
    set +e
    (
        cd "$project_dir"
        UV_CACHE_DIR="$work_dir/$cache_name" "$uv_bin" lock
    ) >"$stdout" 2>"$stderr"
    local status=$?
    set -e
    printf '%s' "$status"
}

printf '%s\n' '=== control A: root project owns its implicit index ==='
root_project="$work_dir/root-project"
write_project "$root_project" root-project
cat >>"$root_project/pyproject.toml" <<EOF

[[tool.uv.index]]
name = "empty-root"
url = "$empty_index"
default = true
EOF
(
    cd "$root_project"
    UV_CACHE_DIR="$work_dir/cache-root-add" \
        "$uv_bin" add --no-sync --index "$populated_index" fieldwork-demo
)
grep -F "$populated_index" "$root_project/pyproject.toml"
root_status=$(run_clean_lock \
    "$root_project" cache-root-lock \
    "$work_dir/root-lock.stdout" "$work_dir/root-lock.stderr")
test "$root_status" -eq 0

printf '%s\n' '=== discriminator B: member receives an unusable implicit index ==='
implicit_workspace="$work_dir/workspace-implicit"
write_workspace "$implicit_workspace"
cp "$implicit_workspace/pyproject.toml" "$implicit_workspace/root.before.toml"
(
    cd "$implicit_workspace"
    UV_CACHE_DIR="$work_dir/cache-member-implicit-add" \
        "$uv_bin" add --package child --no-sync \
        --index "$populated_index" fieldwork-demo
)
cmp "$implicit_workspace/root.before.toml" "$implicit_workspace/pyproject.toml"
grep -F '[[tool.uv.index]]' "$implicit_workspace/child/pyproject.toml"
grep -F "$populated_index" "$implicit_workspace/child/pyproject.toml"
! grep -F "$populated_index" "$implicit_workspace/pyproject.toml"
grep -F 'fieldwork-demo' "$implicit_workspace/child/pyproject.toml"
implicit_status=$(run_clean_lock \
    "$implicit_workspace" cache-member-implicit-lock \
    "$work_dir/member-implicit-lock.stdout" \
    "$work_dir/member-implicit-lock.stderr")
test "$implicit_status" -ne 0
grep -F 'fieldwork-demo' "$work_dir/member-implicit-lock.stderr"

printf '%s\n' '=== control C: one named index is pinned as the package source ==='
named_workspace="$work_dir/workspace-named"
write_workspace "$named_workspace"
cp "$named_workspace/pyproject.toml" "$named_workspace/root.before.toml"
(
    cd "$named_workspace"
    UV_CACHE_DIR="$work_dir/cache-member-named-add" \
        "$uv_bin" add --package child --no-sync \
        --index "fieldwork-local=$populated_index" fieldwork-demo
)
cmp "$named_workspace/root.before.toml" "$named_workspace/pyproject.toml"
grep -F 'name = "fieldwork-local"' "$named_workspace/child/pyproject.toml"
grep -F "$populated_index" "$named_workspace/child/pyproject.toml"
grep -F 'fieldwork-demo = { index = "fieldwork-local" }' \
    "$named_workspace/child/pyproject.toml"
named_status=$(run_clean_lock \
    "$named_workspace" cache-member-named-lock \
    "$work_dir/member-named-lock.stdout" \
    "$work_dir/member-named-lock.stderr")
test "$named_status" -eq 0

printf '%s\n' '--- root-project clean lock stderr ---'
cat "$work_dir/root-lock.stderr"
printf '%s\n' '--- member implicit pyproject.toml ---'
cat "$implicit_workspace/child/pyproject.toml"
printf '%s\n' '--- member implicit clean lock stderr ---'
cat "$work_dir/member-implicit-lock.stderr"
printf '%s\n' '--- member named pyproject.toml ---'
cat "$named_workspace/child/pyproject.toml"
printf '%s\n' '--- member named clean lock stderr ---'
cat "$work_dir/member-named-lock.stderr"
printf '%s\n' '--- local index requests ---'
cat "$server_log"

printf '%s\n' 'root-owned and named-source controls pass; member implicit index is not reusable'
