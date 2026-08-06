#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 UV_BIN VARIANT ARTIFACT_DIR" >&2
    exit 2
fi

uv_bin=$(realpath "$1")
variant=$2
artifact_dir=$(realpath -m "$3")
work_dir="${RUNNER_TEMP:-/tmp}/fieldwork-uv-20678-root-$variant"
index_root="$work_dir/index"
port_file="$work_dir/http-port"
server_log="$artifact_dir/$variant-http.log"
summary="$artifact_dir/$variant-summary.txt"

rm -rf "$work_dir"
mkdir -p "$index_root/simple/fieldwork-demo" "$index_root/empty" "$index_root/files" "$artifact_dir"

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
populated_index="http://127.0.0.1:$port/simple"
empty_index="http://127.0.0.1:$port/empty"

write_project() {
    local project_dir=$1
    local project_name=$2
    mkdir -p "$project_dir"
    cat >"$project_dir/pyproject.toml" <<EOF
[project]
name = "$project_name"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []
EOF
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

lock_status=
run_clean_lock() {
    local label=$1
    local project_dir=$2
    rm -f "$project_dir/uv.lock"
    set +e
    (
        cd "$project_dir"
        UV_CACHE_DIR="$work_dir/cache-$label" UV_NO_PROGRESS=1 "$uv_bin" lock
    ) >"$artifact_dir/$variant-$label.stdout" 2>"$artifact_dir/$variant-$label.stderr"
    lock_status=$?
    set -e
    printf '%s=%s\n' "$label" "$lock_status" >>"$summary"
}

: >"$summary"
printf 'variant=%s\nuv=%s\n' "$variant" "$uv_bin" >>"$summary"
"$uv_bin" --version >>"$summary"

root_project="$work_dir/root-project"
write_project "$root_project" root-project
(
    cd "$root_project"
    UV_CACHE_DIR="$work_dir/cache-root-add" "$uv_bin" add --frozen \
        --index "$populated_index" fieldwork-demo
)
grep -F "$populated_index" "$root_project/pyproject.toml"
run_clean_lock root-owned "$root_project"
root_status=$lock_status

implicit_workspace="$work_dir/workspace-implicit"
write_workspace "$implicit_workspace"
(
    cd "$implicit_workspace"
    UV_CACHE_DIR="$work_dir/cache-implicit-add" "$uv_bin" add --package child --frozen \
        --index "$populated_index" fieldwork-demo
)
run_clean_lock member-implicit "$implicit_workspace"
implicit_status=$lock_status

named_workspace="$work_dir/workspace-named"
write_workspace "$named_workspace"
(
    cd "$named_workspace"
    UV_CACHE_DIR="$work_dir/cache-named-add" "$uv_bin" add --package child --frozen \
        --index "fieldwork-local=$populated_index" fieldwork-demo
)
grep -F 'fieldwork-demo = { index = "fieldwork-local" }' \
    "$named_workspace/child/pyproject.toml"
run_clean_lock member-named "$named_workspace"
named_status=$lock_status

case "$variant" in
    base)
        test "$root_status" -eq 0
        test "$implicit_status" -ne 0
        test "$named_status" -eq 0
        test -z "$(grep -F "$populated_index" "$implicit_workspace/pyproject.toml" || true)"
        grep -F "$populated_index" "$implicit_workspace/child/pyproject.toml"
        ;;
    candidate)
        test "$root_status" -eq 0
        test "$implicit_status" -eq 0
        test "$named_status" -eq 0
        grep -F "$populated_index" "$implicit_workspace/pyproject.toml"
        test -z "$(grep -F "$populated_index" "$implicit_workspace/child/pyproject.toml" || true)"
        ;;
    *)
        echo "unknown variant: $variant" >&2
        exit 2
        ;;
esac

printf 'root_status=%s\nimplicit_status=%s\nnamed_status=%s\n' \
    "$root_status" "$implicit_status" "$named_status" >>"$summary"
cat "$summary"
