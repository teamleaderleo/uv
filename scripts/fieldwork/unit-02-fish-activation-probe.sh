#!/bin/sh
set -eu

mode=${1:?usage: unit-02-fish-activation-probe.sh MODE}
case "$mode" in
  gnu|busybox|macos) ;;
  *) echo "unsupported mode: $mode" >&2; exit 2 ;;
esac

command -v fish >/dev/null

root=$(mktemp -d "${TMPDIR:-/tmp}/uv-unit-02-fish-activation.XXXXXX")
trap 'rm -rf "$root"' EXIT HUP INT TERM

write_variant() {
  variant=$1
  variant_root="$root/$variant"
  mkdir -p "$variant_root/venv/bin" "$variant_root/venv space/bin" "$variant_root/links"

  case "$variant" in
    current)
      cat > "$variant_root/activate-body.fish" <<'FISH'
set -gx VIRTUAL_ENV ''(dirname -- (dirname -- (realpath -- (status -f))))''
printf 'virtual_env=%s\n' "$VIRTUAL_ENV"
FISH
      ;;
    candidate)
      cat > "$variant_root/activate-body.fish" <<'FISH'
set -gx VIRTUAL_ENV ''(dirname -- (dirname -- (realpath (status -f))))''
printf 'virtual_env=%s\n' "$VIRTUAL_ENV"
FISH
      ;;
  esac

  cp "$variant_root/activate-body.fish" "$variant_root/venv/bin/activate.fish"
  cp "$variant_root/activate-body.fish" "$variant_root/venv/bin/-activate.fish"
  cp "$variant_root/activate-body.fish" "$variant_root/venv space/bin/activate.fish"
  ln -s ../venv/bin/activate.fish "$variant_root/links/activate-link.fish"
}

write_variant current
write_variant candidate

run_case() {
  variant=$1
  name=$2
  variant_root="$root/$variant"
  expected=$3
  out="$variant_root/$name.out"
  err="$variant_root/$name.err"

  set +e
  case "$name" in
    absolute)
      fish -c 'source "$argv[1]"' "$variant_root/venv/bin/activate.fish" >"$out" 2>"$err"
      ;;
    relative)
      (cd "$variant_root" && fish -c 'source ./venv/bin/activate.fish') >"$out" 2>"$err"
      ;;
    space)
      (cd "$variant_root" && fish -c 'source "./venv space/bin/activate.fish"') >"$out" 2>"$err"
      ;;
    leading-hyphen)
      (cd "$variant_root/venv/bin" && fish -c 'source ./-activate.fish') >"$out" 2>"$err"
      ;;
    symlink)
      fish -c 'source "$argv[1]"' "$variant_root/links/activate-link.fish" >"$out" 2>"$err"
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
  variant_root="$root/$variant"
  expected_venv=$(realpath "$variant_root/venv")
  expected_space=$(realpath "$variant_root/venv space")
  run_case "$variant" absolute "$expected_venv"
  run_case "$variant" relative "$expected_venv"
  run_case "$variant" space "$expected_space"
  run_case "$variant" leading-hyphen "$expected_venv"
  run_case "$variant" symlink "$expected_venv"
done

printf 'UNIT_02_FISH_ACTIVATION=%s\n' "$mode"
