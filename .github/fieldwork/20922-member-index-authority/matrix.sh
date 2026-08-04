#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 UV_BIN VARIANT ARTIFACT_DIR" >&2
    exit 2
fi

uv_bin=$(realpath "$1")
variant=$2
artifact_dir=$(realpath -m "$3")
work_dir="${RUNNER_TEMP:-/tmp}/fieldwork-uv-20922-$variant"
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
base_url="http://127.0.0.1:$port"
populated_index="$base_url/simple"
empty_index="$base_url/empty"

write_project() {
    local project_dir=$1
    local project_name=$2
    local dependency=${3:-}
    mkdir -p "$project_dir"
    cat >"$project_dir/pyproject.toml" <<EOF
[project]
name = "$project_name"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [$dependency]
EOF
}

run_lock() {
    local label=$1
    local project_dir=$2
    local stdout="$artifact_dir/$variant-$label.stdout"
    local stderr="$artifact_dir/$variant-$label.stderr"
    rm -f "$project_dir/uv.lock"
    set +e
    (
        cd "$project_dir"
        UV_CACHE_DIR="$work_dir/cache-$label" UV_NO_PROGRESS=1 "$uv_bin" lock
    ) >"$stdout" 2>"$stderr"
    local status=$?
    set -e
    printf '%s\n' "$label=$status" >>"$summary"
    return "$status"
}

: >"$summary"
printf 'variant=%s\nuv=%s\n' "$variant" "$uv_bin" >>"$summary"
"$uv_bin" --version >>"$summary"

# Control A: a root-owned index is available to the root project.
root_project="$work_dir/root-project"
write_project "$root_project" root-project '"fieldwork-demo"'
cat >>"$root_project/pyproject.toml" <<EOF

[[tool.uv.index]]
url = "$populated_index"
default = true
EOF
run_lock root-owned "$root_project"

# Discriminator B: the dependency and index are declared by the same member.
direct_workspace="$work_dir/direct-workspace"
mkdir -p "$direct_workspace/child"
cat >"$direct_workspace/pyproject.toml" <<EOF
[tool.uv.workspace]
members = ["child"]

[[tool.uv.index]]
url = "$empty_index"
default = true
EOF
write_project "$direct_workspace/child" child '"fieldwork-demo"'
cat >>"$direct_workspace/child/pyproject.toml" <<EOF

[[tool.uv.index]]
name = "child-index"
url = "$populated_index"
EOF
set +e
run_lock direct-member "$direct_workspace"
direct_status=$?
set -e

# Discriminator C: an unrelated sibling owns the only usable index.
sibling_workspace="$work_dir/sibling-workspace"
mkdir -p "$sibling_workspace/consumer" "$sibling_workspace/index-owner"
cat >"$sibling_workspace/pyproject.toml" <<EOF
[tool.uv.workspace]
members = ["consumer", "index-owner"]

[[tool.uv.index]]
url = "$empty_index"
default = true
EOF
write_project "$sibling_workspace/consumer" consumer '"fieldwork-demo"'
write_project "$sibling_workspace/index-owner" index-owner
cat >>"$sibling_workspace/index-owner/pyproject.toml" <<EOF

[[tool.uv.index]]
name = "owner-index"
url = "$populated_index"
EOF
set +e
run_lock sibling-owned "$sibling_workspace"
sibling_status=$?
set -e

# Control D: a named source pin remains usable from the declaring member.
named_workspace="$work_dir/named-workspace"
mkdir -p "$named_workspace/child"
cat >"$named_workspace/pyproject.toml" <<EOF
[tool.uv.workspace]
members = ["child"]

[[tool.uv.index]]
url = "$empty_index"
default = true
EOF
write_project "$named_workspace/child" child '"fieldwork-demo"'
cat >>"$named_workspace/child/pyproject.toml" <<EOF

[tool.uv.sources]
fieldwork-demo = { index = "child-index" }

[[tool.uv.index]]
name = "child-index"
url = "$populated_index"
explicit = true
EOF
run_lock named-source "$named_workspace"

case "$variant" in
    base)
        test "$direct_status" -ne 0
        test "$sibling_status" -ne 0
        ;;
    candidate)
        test "$direct_status" -eq 0
        test "$sibling_status" -eq 0
        ;;
    *)
        echo "unknown variant: $variant" >&2
        exit 2
        ;;
esac

printf 'direct_member_status=%s\nsibling_owned_status=%s\n' \
    "$direct_status" "$sibling_status" >>"$summary"

cat "$summary"
printf '%s\n' "matrix complete for $variant"
