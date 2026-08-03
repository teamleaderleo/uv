#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TOOL="$ROOT/tool"
AMBIENT="$ROOT/ambient"

run_case() {
    printf '\n== %s ==\n' "$1"
    shift
    "$@"
}

run_case clean \
    env -u PYTHONPATH uvx --from "$TOOL" fieldwork-uvx-probe

run_case ambient-pythonpath \
    env PYTHONPATH="$AMBIENT" uvx --from "$TOOL" fieldwork-uvx-probe

run_case isolated-ambient-pythonpath \
    env PYTHONPATH="$AMBIENT" uvx --isolated --from "$TOOL" fieldwork-uvx-probe

run_case sanitized \
    env -u PYTHONPATH PYTHONNOUSERSITE=1 uvx --isolated --from "$TOOL" fieldwork-uvx-probe

# Record the complete executable and path output. Do not reduce this to a
# version-only assertion until the source of any contamination is established.
