#!/usr/bin/env bash
set -euo pipefail

uv_bin=${1:?uv binary}
variant=${2:?baseline or active-pr}
out=${3:?output directory}

uv_bin=$(realpath "$uv_bin")
mkdir -p "$out"
out=$(realpath "$out")
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/uv-stubs-backends.XXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM

backends=(uv hatch flit pdm poetry setuptools maturin scikit)
printf 'variant\tbackend\tinit_status\tbuild_status\thyphen_pyi\thyphen_py\tunderscore_py\tproject_scripts\n' >"$out/summary.tsv"

for backend in "${backends[@]}"; do
    case_dir="$out/$backend"
    project="$work/$backend/foo-stubs"
    mkdir -p "$case_dir" "$(dirname "$project")"

    init_status=0
    "$uv_bin" init --package --build-backend "$backend" "$project" \
        >"$case_dir/init.stdout" 2>"$case_dir/init.stderr" || init_status=$?
    printf '%d\n' "$init_status" >"$case_dir/init.status"

    if [[ "$init_status" != 0 ]]; then
        printf '%s\t%s\t%d\tNA\t0\t0\t0\t0\n' \
            "$variant" "$backend" "$init_status" >>"$out/summary.tsv"
        continue
    fi

    find "$project" -path "$project/.git" -prune -o -type f -printf '%P\n' \
        | LC_ALL=C sort >"$case_dir/files.txt"
    cp "$project/pyproject.toml" "$case_dir/pyproject.toml"

    hyphen_pyi=0
    hyphen_py=0
    underscore_py=0
    project_scripts=0
    [[ -f "$project/src/foo-stubs/__init__.pyi" ]] && hyphen_pyi=1
    [[ -f "$project/src/foo-stubs/__init__.py" ]] && hyphen_py=1
    [[ -f "$project/src/foo_stubs/__init__.py" ]] && underscore_py=1
    grep -q '^\[project\.scripts\]$' "$project/pyproject.toml" && project_scripts=1 || true

    if [[ -f "$project/src/foo-stubs/__init__.py" ]]; then
        cp "$project/src/foo-stubs/__init__.py" "$case_dir/hyphen-init.py"
    fi
    if [[ -f "$project/src/foo-stubs/__init__.pyi" ]]; then
        cp "$project/src/foo-stubs/__init__.pyi" "$case_dir/hyphen-init.pyi"
    fi
    if [[ -f "$project/src/foo_stubs/__init__.py" ]]; then
        cp "$project/src/foo_stubs/__init__.py" "$case_dir/underscore-init.py"
    fi

    build_status=0
    (
        cd "$project"
        timeout 360s "$uv_bin" build --no-progress
    ) >"$case_dir/build.stdout" 2>"$case_dir/build.stderr" || build_status=$?
    printf '%d\n' "$build_status" >"$case_dir/build.status"

    if [[ -d "$project/dist" ]]; then
        find "$project/dist" -maxdepth 1 -type f -printf '%f\n' \
            | LC_ALL=C sort >"$case_dir/dist-files.txt"
    fi

    printf '%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\n' \
        "$variant" "$backend" "$init_status" "$build_status" \
        "$hyphen_pyi" "$hyphen_py" "$underscore_py" "$project_scripts" \
        >>"$out/summary.tsv"

done

python3 - "$variant" "$out/summary.tsv" <<'PY'
from __future__ import annotations

import csv
import sys
from pathlib import Path

variant = sys.argv[1]
path = Path(sys.argv[2])
rows = {row["backend"]: row for row in csv.DictReader(path.open(), delimiter="\t")}
expected = {"uv", "hatch", "flit", "pdm", "poetry", "setuptools", "maturin", "scikit"}
assert rows.keys() == expected, rows.keys()
assert all(row["init_status"] == "0" for row in rows.values()), rows

if variant == "baseline":
    assert all(row["underscore_py"] == "1" for row in rows.values()), rows
    assert all(row["hyphen_pyi"] == "0" and row["hyphen_py"] == "0" for row in rows.values()), rows
    assert rows["uv"]["build_status"] != "0", rows["uv"]
elif variant == "active-pr":
    uv = rows["uv"]
    assert uv["hyphen_pyi"] == "1" and uv["hyphen_py"] == "0" and uv["underscore_py"] == "0", uv
    assert uv["project_scripts"] == "0", uv
    assert uv["build_status"] == "0", uv

    for backend, row in rows.items():
        if backend == "uv":
            continue
        assert row["hyphen_py"] == "1" and row["underscore_py"] == "0", (backend, row)
        assert row["project_scripts"] == "0", (backend, row)
else:
    raise AssertionError(variant)
PY

cat "$out/summary.tsv"
