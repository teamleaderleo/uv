#!/bin/sh
set -eu

uv=${1:?usage: script-lock-symlink-authority.sh UV_BINARY}
case "$uv" in
  /*) ;;
  *) uv=$(cd "$(dirname "$uv")" && pwd)/$(basename "$uv") ;;
esac

test -x "$uv"

root=$(mktemp -d "${TMPDIR:-/tmp}/uv-script-lock-authority.XXXXXX")
cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  rm -rf "$root"
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

export UV_OFFLINE=1
export UV_PYTHON_DOWNLOADS=never
export UV_NO_PROGRESS=1
export UV_PYTHON=${UV_PYTHON:-$(command -v python3)}

mkdir -p "$root/source" "$root/alias-a" "$root/alias-b"
cat > "$root/source/tool.py" <<'PY'
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
print("SCRIPT_OK")
PY

canonical_script="$root/source/tool.py"
canonical_lock="$canonical_script.lock"
alias_a="$root/alias-a/tool.py"
alias_b="$root/alias-b/tool.py"
alias_a_lock="$alias_a.lock"
alias_b_lock="$alias_b.lock"

ln -s ../source/tool.py "$alias_a"
ln -s ../source/tool.py "$alias_b"

run_capture() {
  label=$1
  shift
  stdout="$root/$label.stdout"
  stderr="$root/$label.stderr"
  set +e
  "$@" >"$stdout" 2>"$stderr"
  status=$?
  set -e
  printf 'CASE=%s STATUS=%s\n' "$label" "$status"
  sed 's/^/STDOUT: /' "$stdout"
  sed 's/^/STDERR: /' "$stderr"
  return "$status"
}

# Establish one canonical lock with no dependency network traffic.
run_capture canonical-lock "$uv" lock --script "$canonical_script"
test -f "$canonical_lock"
canonical_digest=$(sha256sum "$canonical_lock" | cut -d' ' -f1)
printf 'CANONICAL_DIGEST=%s\n' "$canonical_digest"

run_capture canonical-run "$uv" run --locked --script "$canonical_script"
grep -Fx 'SCRIPT_OK' "$root/canonical-run.stdout" >/dev/null

# Current behavior ignores the canonical lock when invoked through an alias.
if run_capture alias-a-no-local-lock "$uv" run --locked --script "$alias_a"; then
  echo 'alias unexpectedly used canonical lock' >&2
  exit 1
fi
grep -F 'Unable to find lockfile for Python script' "$root/alias-a-no-local-lock.stderr" >/dev/null

# A byte-for-byte copied alias-side lock becomes authoritative for that spelling.
cp "$canonical_lock" "$alias_a_lock"
run_capture alias-a-copied-lock "$uv" run --locked --script "$alias_a"
grep -Fx 'SCRIPT_OK' "$root/alias-a-copied-lock.stdout" >/dev/null

# Another alias to the same source can select a different, malformed authority.
printf 'version = "not-a-lock"\n' > "$alias_b_lock"
if run_capture alias-b-malformed-lock "$uv" run --locked --script "$alias_b"; then
  echo 'malformed alias lock unexpectedly succeeded' >&2
  exit 1
fi
grep -F 'Failed to parse `uv.lock`' "$root/alias-b-malformed-lock.stderr" >/dev/null
grep -F 'invalid type:' "$root/alias-b-malformed-lock.stderr" >/dev/null

# The write path also follows invocation spelling, leaving the canonical lock untouched.
rm -f "$alias_a_lock"
run_capture alias-a-write "$uv" lock --script "$alias_a"
test -f "$alias_a_lock"
test "$(sha256sum "$canonical_lock" | cut -d' ' -f1)" = "$canonical_digest"

# The same source now has two independently addressable lock locations.
printf 'CANONICAL_LOCK=%s\n' "$canonical_lock"
printf 'ALIAS_A_LOCK=%s\n' "$alias_a_lock"
printf 'ALIAS_B_LOCK=%s\n' "$alias_b_lock"
printf 'FIELDWORK_312=invocation-path-authority\n'
