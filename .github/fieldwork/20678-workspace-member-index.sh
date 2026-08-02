#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
uv_bin="$repo_root/target/debug/uv"
work_dir="${RUNNER_TEMP:-/tmp}/fieldwork-uv-20678"
index_root="$work_dir/index"
workspace="$work_dir/workspace"
port_file="$work_dir/http-port"
server_log="$work_dir/http.log"

rm -rf "$work_dir"
mkdir -p "$index_root/simple/fieldwork-demo" "$index_root/empty" "$index_root/files" "$workspace/child/src/child"

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

cat >"$workspace/pyproject.toml" <<EOF
[tool.uv.workspace]
members = ["child"]

[[tool.uv.index]]
name = "empty-root"
url = "$base_url/empty"
default = true
EOF
cp "$workspace/pyproject.toml" "$workspace/root.before.toml"

cat >"$workspace/child/pyproject.toml" <<'TOML'
[project]
name = "child"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["uv_build>=0.8.0,<0.9.0"]
build-backend = "uv_build"
TOML
printf '%s\n' '__version__ = "0.1.0"' >"$workspace/child/src/child/__init__.py"

(
    cd "$workspace"
    UV_CACHE_DIR="$work_dir/cache-add" \
        "$uv_bin" add --package child --no-sync \
        --index "$base_url/simple" fieldwork-demo
)

cmp "$workspace/root.before.toml" "$workspace/pyproject.toml"
grep -F '[[tool.uv.index]]' "$workspace/child/pyproject.toml"
grep -F "$base_url/simple" "$workspace/child/pyproject.toml"
! grep -F "$base_url/simple" "$workspace/pyproject.toml"
grep -F 'fieldwork-demo' "$workspace/child/pyproject.toml"

rm -f "$workspace/uv.lock"
set +e
(
    cd "$workspace"
    UV_CACHE_DIR="$work_dir/cache-lock" "$uv_bin" lock
) >"$work_dir/lock.stdout" 2>"$work_dir/lock.stderr"
lock_status=$?
set -e

printf '%s\n' '--- root pyproject.toml ---'
cat "$workspace/pyproject.toml"
printf '%s\n' '--- member pyproject.toml ---'
cat "$workspace/child/pyproject.toml"
printf '%s\n' '--- clean lock stdout ---'
cat "$work_dir/lock.stdout"
printf '%s\n' '--- clean lock stderr ---'
cat "$work_dir/lock.stderr"
printf 'lock_status=%s\n' "$lock_status"
printf '%s\n' '--- local index requests ---'
cat "$server_log"

# Current behavior: the CLI index is persisted in the selected member, but a
# clean workspace lock consults root index authority and cannot resolve the
# dependency from the member-only index.
test "$lock_status" -ne 0
grep -F 'fieldwork-demo' "$work_dir/lock.stderr"

printf '%s\n' 'workspace member index authority mismatch reproduced'
