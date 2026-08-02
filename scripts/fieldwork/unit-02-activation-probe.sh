#!/usr/bin/env bash
set -euo pipefail

mode=${1:?usage: unit-02-activation-probe.sh MODE}
case "$mode" in
  gnu|busybox|macos) ;;
  *) echo "unsupported mode: $mode" >&2; exit 2 ;;
esac

root=$(mktemp -d "${TMPDIR:-/tmp}/uv-unit-02-activation.XXXXXX")
trap 'rm -rf "$root"' EXIT HUP INT TERM

mkdir -p "$root/venv/bin" "$root/venv space/bin" "$root/links"

cat > "$root/activate-body" <<'EOF'
if [ -n "${BASH_VERSION:+x}" ]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
else
  echo "probe requires bash" >&2
  return 40
fi

case "${UNIT_02_VARIANT:?}" in
  current)
    VIRTUAL_ENV="$(dirname -- "$(dirname -- "$(realpath -- "$SCRIPT_PATH")")")"
    ;;
  candidate)
    VIRTUAL_ENV="$(dirname -- "$(dirname -- "$(realpath "$SCRIPT_PATH")")")"
    ;;
  *)
    echo "bad variant: $UNIT_02_VARIANT" >&2
    return 41
    ;;
esac

printf 'virtual_env=%s\n' "$VIRTUAL_ENV"
EOF

cp "$root/activate-body" "$root/venv/bin/activate"
cp "$root/activate-body" "$root/venv/bin/-activate"
cp "$root/activate-body" "$root/venv space/bin/activate"
ln -s ../venv/bin/activate "$root/links/activate-link"

expected_venv=$(realpath "$root/venv")
expected_space=$(realpath "$root/venv space")

run_case() {
  variant=$1
  name=$2
  expected=$3
  out="$root/${variant}-${name}.out"
  err="$root/${variant}-${name}.err"

  set +e
  case "$name" in
    absolute)
      UNIT_02_VARIANT=$variant bash -c 'source "$1"' _ "$root/venv/bin/activate" >"$out" 2>"$err"
      ;;
    relative)
      (cd "$root" && UNIT_02_VARIANT=$variant bash -c 'source ./venv/bin/activate') >"$out" 2>"$err"
      ;;
    path)
      PATH="$root/venv/bin:$PATH" UNIT_02_VARIANT=$variant bash -c 'source activate' >"$out" 2>"$err"
      ;;
    space)
      (cd "$root" && UNIT_02_VARIANT=$variant bash -c 'source "./venv space/bin/activate"') >"$out" 2>"$err"
      ;;
    leading-hyphen)
      (cd "$root/venv/bin" && UNIT_02_VARIANT=$variant bash -c 'source ./-activate') >"$out" 2>"$err"
      ;;
    symlink)
      UNIT_02_VARIANT=$variant bash -c 'source "$1"' _ "$root/links/activate-link" >"$out" 2>"$err"
      ;;
  esac
  status=$?
  set -e

  printf 'mode=%s variant=%s case=%s status=%s\n' "$mode" "$variant" "$name" "$status"
  sed 's/^/stdout: /' "$out"
  sed 's/^/stderr: /' "$err"

  test "$status" -eq 0
  test "$(cat "$out")" = "virtual_env=$expected"

  if [ "$mode" = busybox ] && [ "$variant" = current ]; then
    grep -F 'realpath: --:' "$err" >/dev/null
  else
    test ! -s "$err"
  fi
}

for variant in current candidate; do
  run_case "$variant" absolute "$expected_venv"
  run_case "$variant" relative "$expected_venv"
  run_case "$variant" path "$expected_venv"
  run_case "$variant" space "$expected_space"
  run_case "$variant" leading-hyphen "$expected_venv"
  run_case "$variant" symlink "$expected_venv"
done

printf 'UNIT_02_ACTIVATION=%s\n' "$mode"
