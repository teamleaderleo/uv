#!/usr/bin/env bash
set -euo pipefail

: "${UV_VERSION:?UV_VERSION must be set}"

root="${RUNNER_TEMP:-/tmp}/uv-source-authority-${UV_VERSION}"
results="$root/results.jsonl"
summary="$root/summary.md"
rm -rf "$root"
mkdir -p "$root"
: > "$results"

make_fixture() {
  local case_dir=$1
  local order=$2

  mkdir -p "$case_dir/project" "$case_dir/parent" "$case_dir/child/child"
  : > "$case_dir/child/child/__init__.py"

  cat > "$case_dir/child/pyproject.toml" <<'EOF'
[project]
name = "child"
version = "0.1.0"
requires-python = ">=3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
EOF

  cat > "$case_dir/parent/pyproject.toml" <<'EOF'
[project]
name = "parent"
version = "0.1.0"
requires-python = ">=3.12"
dynamic = ["dependencies"]

[build-system]
requires = []
build-backend = "backend"
backend-path = ["."]
EOF

  cat > "$case_dir/parent/backend.py" <<'PY'
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

NAME = "parent"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
METADATA = """Metadata-Version: 2.3
Name: parent
Version: 0.1.0
Requires-Python: >=3.12
Requires-Dist: child @ file:../child
"""
WHEEL = """Wheel-Version: 1.0
Generator: uv-fieldwork-authority-backend
Root-Is-Purelib: true
Tag: py3-none-any
"""


def _write_metadata(root: Path) -> str:
    dist_info = root / DIST_INFO
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(METADATA)
    (dist_info / "WHEEL").write_text(WHEEL)
    return DIST_INFO


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    return _write_metadata(Path(metadata_directory))


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_name = f"{NAME}-{VERSION}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    members = {
        "parent/__init__.py": "",
        f"{DIST_INFO}/METADATA": METADATA,
        f"{DIST_INFO}/WHEEL": WHEEL,
    }
    record = io.StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for path in members:
        writer.writerow((path, "", ""))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    members[f"{DIST_INFO}/RECORD"] = record.getvalue()
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as wheel:
        for path, content in members.items():
            wheel.writestr(path, content)
    return wheel_name
PY

  if [[ "$order" == parent-first ]]; then
    dependencies='dependencies = ["parent", "child"]'
  else
    dependencies='dependencies = ["child", "parent"]'
  fi

  local child_absolute
  child_absolute=$(python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve())' "$case_dir/child")

  cat > "$case_dir/project/pyproject.toml" <<EOF
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
$dependencies

[tool.uv.sources]
parent = { path = "../parent" }
child = { path = "$child_absolute" }
EOF

  # Prove that the lower-authority parent metadata actually carries the
  # relative direct URL under test. A nested tool.uv.sources table is not a
  # sufficient fixture because build metadata may omit it entirely.
  python3 - "$case_dir/parent" "$case_dir/preflight-metadata" <<'PY'
import pathlib
import sys

parent = pathlib.Path(sys.argv[1])
metadata_root = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(parent))
import backend

dist_info = backend.prepare_metadata_for_build_wheel(metadata_root)
metadata = (metadata_root / dist_info / "METADATA").read_text()
expected = "Requires-Dist: child @ file:../child"
if expected not in metadata.splitlines():
    raise SystemExit(f"missing exact relative metadata requirement: {expected!r}\n{metadata}")
print(expected)
PY
}

record_lock() {
  local case_dir=$1
  local order=$2

  python3 - "$case_dir/project/uv.lock" "$case_dir" "$UV_VERSION" "$order" >> "$results" <<'PY'
import json
import os
import pathlib
import sys
import tomllib

lock_path, case_dir, uv_version, order = sys.argv[1:]
case_root = pathlib.Path(case_dir)
data = tomllib.loads(pathlib.Path(lock_path).read_text())
packages = {package["name"]: package for package in data["package"]}
child = packages["child"]
parent = packages["parent"]
source = child.get("source", {})
requires_dist = parent.get("metadata", {}).get("requires-dist", [])
parent_child = next((item for item in requires_dist if item.get("name") == "child"), None)
if parent_child is None:
    raise SystemExit("authority control is invalid: parent metadata has no child requirement")


def path_value(mapping):
    for key in ("editable", "directory", "path"):
        if key in mapping:
            return key, mapping[key]
    return None, None


def normalized(value):
    if not value:
        return value
    path = pathlib.Path(value)
    if not path.is_absolute():
        return value
    try:
        return f"<CASE>/{path.relative_to(case_root).as_posix()}"
    except ValueError:
        return f"<ABS>/{path.name}"


source_kind, source_path = path_value(source)
metadata_kind, metadata_path = path_value(parent_child)
if source_path is None or metadata_path is None:
    raise SystemExit(
        "authority control is invalid: expected local path in both child source and parent metadata"
    )
print(
    json.dumps(
        {
            "uv_version": uv_version,
            "dependency_order": order,
            "root_child_declaration": "absolute",
            "parent_child_declaration": "relative-generated-metadata",
            "child_source_kind": source_kind,
            "child_source_path": source_path,
            "child_source_normalized": normalized(source_path),
            "child_source_absolute": bool(source_path and os.path.isabs(source_path)),
            "parent_metadata_kind": metadata_kind,
            "parent_metadata_path": metadata_path,
            "parent_metadata_normalized": normalized(metadata_path),
            "parent_metadata_absolute": bool(metadata_path and os.path.isabs(metadata_path)),
        },
        sort_keys=True,
    )
)
PY
}

for order in parent-first child-first; do
  case_dir="$root/$order"
  make_fixture "$case_dir" "$order"
  export UV_CACHE_DIR="$case_dir/cache"
  (
    cd "$case_dir/project"
    uv lock --python 3.12
  )
  record_lock "$case_dir" "$order"
done

python3 - "$results" "$summary" <<'PY'
import json
import pathlib
import sys

records_path, summary_path = map(pathlib.Path, sys.argv[1:])
records = [json.loads(line) for line in records_path.read_text().splitlines() if line]

lines = [
    f"# UV source-authority negative control — {records[0]['uv_version']}",
    "",
    "Root declaration: **absolute**. Generated parent metadata: **relative**.",
    "",
    "| dependency order | child source | parent metadata |",
    "| --- | --- | --- |",
]
for record in records:
    source = f"{record['child_source_kind']}={record['child_source_normalized']}"
    source += " ABSOLUTE" if record["child_source_absolute"] else " RELATIVE"
    metadata = f"{record['parent_metadata_kind']}={record['parent_metadata_normalized']}"
    metadata += " ABSOLUTE" if record["parent_metadata_absolute"] else " RELATIVE"
    lines.append(f"| {record['dependency_order']} | `{source}` | `{metadata}` |")

source_values = {
    (
        record["child_source_kind"],
        record["child_source_normalized"],
        record["child_source_absolute"],
    )
    for record in records
}
metadata_values = {
    (
        record["parent_metadata_kind"],
        record["parent_metadata_normalized"],
        record["parent_metadata_absolute"],
    )
    for record in records
}
lines.extend(
    [
        "",
        f"Dependency-order invariant child source: **{len(source_values) == 1}**.",
        f"Dependency-order invariant parent metadata: **{len(metadata_values) == 1}**.",
        f"Absolute child source records: **{sum(record['child_source_absolute'] for record in records)}/{len(records)}**.",
        f"Absolute parent metadata records: **{sum(record['parent_metadata_absolute'] for record in records)}/{len(records)}**.",
    ]
)
summary_path.write_text("\n".join(lines) + "\n")
PY

cat "$summary"

mkdir -p fieldwork/source-provenance-probe/out-authority
cp "$results" fieldwork/source-provenance-probe/out-authority/results.jsonl
cp "$summary" fieldwork/source-provenance-probe/out-authority/summary.md

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat "$summary" >> "$GITHUB_STEP_SUMMARY"
fi
