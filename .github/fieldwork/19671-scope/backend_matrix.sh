#!/usr/bin/env bash
set -euo pipefail

uv_bin=${1:?uv binary}
out=${2:?output directory}

uv_bin=$(realpath "$uv_bin")
mkdir -p "$out"
out=$(realpath "$out")
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/uv-stubs-scope.XXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM

backends=(uv hatch flit pdm poetry setuptools maturin scikit)
kinds=(package lib)
printf 'kind\tbackend\tinit_status\tbuild_status\thyphen_pyi\thyphen_py\tunderscore_py\tproject_scripts\n' >"$out/summary.tsv"

for kind in "${kinds[@]}"; do
    for backend in "${backends[@]}"; do
        case_dir="$out/$kind/$backend"
        project="$work/$kind/$backend/foo-stubs"
        mkdir -p "$case_dir" "$(dirname "$project")"

        init_status=0
        "$uv_bin" init "--$kind" --build-backend "$backend" "$project" \
            >"$case_dir/init.stdout" 2>"$case_dir/init.stderr" || init_status=$?
        printf '%d\n' "$init_status" >"$case_dir/init.status"

        if [[ "$init_status" != 0 ]]; then
            printf '%s\t%s\t%d\tNA\t0\t0\t0\t0\n' \
                "$kind" "$backend" "$init_status" >>"$out/summary.tsv"
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
            "$kind" "$backend" "$init_status" "$build_status" \
            "$hyphen_pyi" "$hyphen_py" "$underscore_py" "$project_scripts" \
            >>"$out/summary.tsv"
    done
done

python3 - "$out/summary.tsv" <<'PY'
from __future__ import annotations

import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = {
    (row["kind"], row["backend"]): row
    for row in csv.DictReader(path.open(), delimiter="\t")
}
backends = {"uv", "hatch", "flit", "pdm", "poetry", "setuptools", "maturin", "scikit"}
expected = {(kind, backend) for kind in ("package", "lib") for backend in backends}
assert rows.keys() == expected, rows.keys()
assert all(row["init_status"] == "0" for row in rows.values()), rows
assert all(row["build_status"] == "0" for row in rows.values()), rows

for kind in ("package", "lib"):
    uv = rows[(kind, "uv")]
    assert uv["hyphen_pyi"] == "1", uv
    assert uv["hyphen_py"] == "0" and uv["underscore_py"] == "0", uv
    assert uv["project_scripts"] == "0", uv

    for backend in backends - {"uv"}:
        row = rows[(kind, backend)]
        assert row["underscore_py"] == "1", (kind, backend, row)
        assert row["hyphen_pyi"] == "0" and row["hyphen_py"] == "0", (kind, backend, row)
        expected_scripts = "1" if kind == "package" else "0"
        assert row["project_scripts"] == expected_scripts, (kind, backend, row)
PY

cat "$out/summary.tsv"
