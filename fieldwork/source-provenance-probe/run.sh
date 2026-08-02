#!/usr/bin/env bash
set -euo pipefail

: "${UV_VERSION:?UV_VERSION must be set}"

root="${RUNNER_TEMP:-/tmp}/uv-source-provenance-${UV_VERSION}"
results="$root/results.jsonl"
summary="$root/summary.md"
rm -rf "$root"
mkdir -p "$root"
: > "$results"

make_fixture() {
  local case_dir=$1
  local mode=$2
  local order=$3

  mkdir -p "$case_dir/project" "$case_dir/parent/parent" "$case_dir/child/child"
  : > "$case_dir/parent/parent/__init__.py"
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

  if [[ "$mode" == editable ]]; then
    cat > "$case_dir/parent/pyproject.toml" <<'EOF'
[tool.poetry]
name = "parent"
version = "0.1.0"
description = ""
packages = [{ include = "parent" }]

[tool.poetry.dependencies]
python = ">=3.12,<3.13"
child = { path = "../child", develop = true }

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF
    parent_source='parent = { path = "../parent", editable = true }'
    child_source='child = { path = "../child", editable = true }'
  else
    cat > "$case_dir/parent/pyproject.toml" <<'EOF'
[tool.poetry]
name = "parent"
version = "0.1.0"
description = ""
packages = [{ include = "parent" }]

[tool.poetry.dependencies]
python = ">=3.12,<3.13"
child = { path = "../child" }

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF
    parent_source='parent = { path = "../parent" }'
    child_source='child = { path = "../child" }'
  fi

  if [[ "$order" == parent-first ]]; then
    dependencies='dependencies = ["parent", "child"]'
  else
    dependencies='dependencies = ["child", "parent"]'
  fi

  cat > "$case_dir/project/pyproject.toml" <<EOF
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
$dependencies

[tool.uv.sources]
$parent_source
$child_source
EOF
}

record_lock() {
  local case_dir=$1
  local mode=$2
  local order=$3
  local cache_state=$4

  python3 - "$case_dir/project/uv.lock" "$case_dir" "$UV_VERSION" "$mode" "$order" "$cache_state" >> "$results" <<'PY'
import json
import os
import pathlib
import sys
import tomllib

lock_path, case_dir, uv_version, mode, order, cache_state = sys.argv[1:]
case_root = pathlib.Path(case_dir)
data = tomllib.loads(pathlib.Path(lock_path).read_text())
packages = {package["name"]: package for package in data["package"]}
child = packages["child"]
parent = packages["parent"]
source = child.get("source", {})
requires_dist = parent.get("metadata", {}).get("requires-dist", [])
parent_child = next((item for item in requires_dist if item.get("name") == "child"), {})

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
record = {
    "uv_version": uv_version,
    "mode": mode,
    "dependency_order": order,
    "cache_state": cache_state,
    "child_source_kind": source_kind,
    "child_source_path": source_path,
    "child_source_normalized": normalized(source_path),
    "child_source_absolute": bool(source_path and os.path.isabs(source_path)),
    "parent_metadata_kind": metadata_kind,
    "parent_metadata_path": metadata_path,
    "parent_metadata_normalized": normalized(metadata_path),
    "parent_metadata_absolute": bool(metadata_path and os.path.isabs(metadata_path)),
}
print(json.dumps(record, sort_keys=True))
PY
}

for mode in editable noneditable; do
  for order in parent-first child-first; do
    case_dir="$root/$mode-$order"
    make_fixture "$case_dir" "$mode" "$order"
    export UV_CACHE_DIR="$case_dir/cache"

    (
      cd "$case_dir/project"
      uv lock --python 3.12
    )
    record_lock "$case_dir" "$mode" "$order" cold

    rm -f "$case_dir/project/uv.lock"
    (
      cd "$case_dir/project"
      uv lock --python 3.12
    )
    record_lock "$case_dir" "$mode" "$order" warm
  done
done

python3 - "$results" "$summary" <<'PY'
import json
import pathlib
import sys

records_path, summary_path = map(pathlib.Path, sys.argv[1:])
records = [json.loads(line) for line in records_path.read_text().splitlines() if line]

lines = [
    f"# UV source-provenance probe — {records[0]['uv_version']}",
    "",
    "| mode | order | cache | child source | parent metadata |",
    "| --- | --- | --- | --- | --- |",
]
for record in records:
    source = f"{record['child_source_kind']}={record['child_source_normalized']}"
    if record["child_source_absolute"]:
        source += " **ABSOLUTE**"
    metadata = f"{record['parent_metadata_kind']}={record['parent_metadata_normalized']}"
    if record["parent_metadata_absolute"]:
        metadata += " **ABSOLUTE**"
    lines.append(
        f"| {record['mode']} | {record['dependency_order']} | {record['cache_state']} | "
        f"`{source}` | `{metadata}` |"
    )

lines.extend(["", "## Invariance checks", ""])
for mode in ("editable", "noneditable"):
    for cache_state in ("cold", "warm"):
        selected = [
            record
            for record in records
            if record["mode"] == mode and record["cache_state"] == cache_state
        ]
        source_values = {
            (
                record["child_source_kind"],
                record["child_source_normalized"],
                record["child_source_absolute"],
            )
            for record in selected
        }
        metadata_values = {
            (
                record["parent_metadata_kind"],
                record["parent_metadata_normalized"],
                record["parent_metadata_absolute"],
            )
            for record in selected
        }
        lines.append(
            f"- `{mode}` / `{cache_state}`: dependency-order invariant source="
            f"`{len(source_values) == 1}`, metadata=`{len(metadata_values) == 1}`."
        )

for mode in ("editable", "noneditable"):
    for order in ("parent-first", "child-first"):
        selected = [
            record
            for record in records
            if record["mode"] == mode and record["dependency_order"] == order
        ]
        source_values = {
            (
                record["child_source_kind"],
                record["child_source_normalized"],
                record["child_source_absolute"],
            )
            for record in selected
        }
        metadata_values = {
            (
                record["parent_metadata_kind"],
                record["parent_metadata_normalized"],
                record["parent_metadata_absolute"],
            )
            for record in selected
        }
        lines.append(
            f"- `{mode}` / `{order}`: cold-warm invariant source="
            f"`{len(source_values) == 1}`, metadata=`{len(metadata_values) == 1}`."
        )

absolute_source = sum(record["child_source_absolute"] for record in records)
absolute_metadata = sum(record["parent_metadata_absolute"] for record in records)
lines.extend(
    [
        "",
        f"Absolute child source records: **{absolute_source}/{len(records)}**.",
        f"Absolute parent metadata records: **{absolute_metadata}/{len(records)}**.",
    ]
)
summary_path.write_text("\n".join(lines) + "\n")
PY

cat "$summary"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat "$summary" >> "$GITHUB_STEP_SUMMARY"
fi

mkdir -p fieldwork/source-provenance-probe/out
cp "$results" fieldwork/source-provenance-probe/out/results.jsonl
cp "$summary" fieldwork/source-provenance-probe/out/summary.md
