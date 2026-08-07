#!/usr/bin/env bash
set -euo pipefail

UV="$1"
ROOT="$2"
rm -rf "$ROOT"
mkdir -p "$ROOT"
TRANSCRIPT="$ROOT/validation.txt"
: > "$TRANSCRIPT"

run_case() {
  local name="$1"
  local expected_code="$2"
  shift 2
  local dir="$ROOT/$name"
  local output code
  set +e
  output="$(cd "$dir" && "$UV" lock 2>&1)"
  code=$?
  set -e
  {
    printf '\n===== %s =====\n' "$name"
    printf 'exit=%s\n' "$code"
    printf '%s\n' "$output"
  } | tee -a "$TRANSCRIPT"
  if [[ "$code" -ne "$expected_code" ]]; then
    printf 'unexpected exit for %s: %s\n' "$name" "$code" >&2
    exit 1
  fi
  CASE_OUTPUT="$output"
}

# The upstream regression: a virtual project has an invalid PEP 508 dependency. `package = false`
# means the project build system is ignored; the parser error should not be replaced by `no-build`.
mkdir -p "$ROOT/virtual-invalid"
cat > "$ROOT/virtual-invalid/pyproject.toml" <<'EOF'
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["anyio<5>"]

[tool.uv]
no-build = true
package = false
EOF
run_case virtual-invalid 1
if grep -q 'Building source distributions' <<<"$CASE_OUTPUT"; then
  echo 'virtual invalid dependency was still masked by a build-disabled error' >&2
  exit 1
fi
if ! grep -q 'anyio<5>' <<<"$CASE_OUTPUT"; then
  echo 'virtual invalid dependency error did not retain the bad requirement text' >&2
  exit 1
fi
if ! grep -Eqi 'parse|specifier|expected' <<<"$CASE_OUTPUT"; then
  echo 'virtual invalid dependency did not expose a parser diagnostic' >&2
  exit 1
fi

# Dynamic dependency metadata is likewise unavailable statically. A virtual project must explain
# that limitation instead of trying the ignored build system.
mkdir -p "$ROOT/virtual-dynamic"
cat > "$ROOT/virtual-dynamic/pyproject.toml" <<'EOF'
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
dynamic = ["dependencies"]

[tool.uv]
no-build = true
package = false
EOF
run_case virtual-dynamic 1
if grep -q 'Building source distributions' <<<"$CASE_OUTPUT"; then
  echo 'virtual dynamic dependency metadata was still masked by no-build' >&2
  exit 1
fi
if ! grep -qi 'dynamic' <<<"$CASE_OUTPUT" || ! grep -qi 'dependencies' <<<"$CASE_OUTPUT"; then
  echo 'virtual dynamic metadata did not expose its static-metadata limitation' >&2
  exit 1
fi

# A virtual project whose required metadata is static should continue to lock under no-build.
mkdir -p "$ROOT/virtual-valid"
cat > "$ROOT/virtual-valid/pyproject.toml" <<'EOF'
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
no-build = true
package = false
EOF
run_case virtual-valid 0

# Negative control: ordinary packages retain the existing backend-fallback policy for the same
# invalid requirement. With builds disabled, that fallback still terminates as a no-build error.
mkdir -p "$ROOT/package-invalid"
cat > "$ROOT/package-invalid/pyproject.toml" <<'EOF'
[project]
name = "project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["anyio<5>"]

[tool.uv]
no-build = true
EOF
run_case package-invalid 1
if ! grep -q 'Building source distributions' <<<"$CASE_OUTPUT"; then
  echo 'ordinary package no longer preserved build fallback semantics' >&2
  exit 1
fi

echo 'VALIDATED: virtual projects surface unavailable static metadata without changing ordinary package fallback' | tee -a "$TRANSCRIPT"
