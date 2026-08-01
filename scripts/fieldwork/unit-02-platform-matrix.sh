#!/bin/sh
set -eu

mode=${1:?usage: unit-02-platform-matrix.sh MODE}
case "$mode" in
  gnu|busybox|macos) ;;
  *) echo "unknown mode: $mode" >&2; exit 2 ;;
esac

root=$(mktemp -d "${TMPDIR:-/tmp}/uv-unit-02-last-mile.XXXXXX")
cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  rm -rf "$root"
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$root/bin" "$root/links"
cat >"$root/bin/python" <<'EOF'
#!/bin/sh
printf 'python=%s\nscript=%s\narg=%s\n' "$0" "$1" "${2-}"
EOF
chmod +x "$root/bin/python"
expected_python=$(realpath "$root/bin/python")

write_launcher() {
  variant=$1
  destination=$2
  case "$variant" in
    current)
      cat >"$destination" <<'EOF'
#!/bin/sh
'''exec' "$(dirname -- "$(realpath -- "$0")")"/'python' "$0" "$@"
' '''
EOF
      ;;
    candidate)
      cat >"$destination" <<'EOF'
#!/bin/sh
'''exec' "$(dirname "$(realpath "$0")")"/'python' "$0" "$@"
' '''
EOF
      ;;
    *) echo "unknown launcher variant: $variant" >&2; exit 2 ;;
  esac
  chmod +x "$destination"
}

run_case() {
  variant=$1
  label=$2
  shift 2
  stdout="$root/$variant-$label.stdout"
  stderr="$root/$variant-$label.stderr"

  set +e
  "$@" >"$stdout" 2>"$stderr"
  status=$?
  set -e

  printf 'mode=%s variant=%s case=%s status=%s\n' "$mode" "$variant" "$label" "$status"
  sed 's/^/stdout: /' "$stdout"
  sed 's/^/stderr: /' "$stderr"

  if [ "$variant" = candidate ]; then
    test "$status" -eq 0
    grep -F "python=$expected_python" "$stdout" >/dev/null
    grep -F 'arg=probe' "$stdout" >/dev/null
    test ! -s "$stderr"
    return
  fi

  case "$mode" in
    gnu)
      test "$status" -eq 0
      grep -F "python=$expected_python" "$stdout" >/dev/null
      grep -F 'arg=probe' "$stdout" >/dev/null
      test ! -s "$stderr"
      ;;
    busybox)
      test "$status" -eq 0
      grep -F "python=$expected_python" "$stdout" >/dev/null
      grep -F 'arg=probe' "$stdout" >/dev/null
      grep -F 'realpath: --' "$stderr" >/dev/null
      ;;
    macos)
      # The baseline is observational here. Candidate behavior is the compatibility gate.
      :
      ;;
  esac
}

for variant in current candidate; do
  write_launcher "$variant" "$root/bin/tool"
  write_launcher "$variant" "$root/bin/tool with space"
  write_launcher "$variant" "$root/bin/-tool"
  ln -sf ../bin/tool "$root/links/tool-link"

  run_case "$variant" absolute "$root/bin/tool" probe
  run_case "$variant" relative sh -c 'cd "$1" && ./bin/tool probe' sh "$root"
  run_case "$variant" path sh -c 'cd "$1" && PATH="$1/bin:$PATH" tool probe' sh "$root"
  run_case "$variant" space sh -c 'cd "$1" && "./bin/tool with space" probe' sh "$root"
  run_case "$variant" leading-hyphen sh -c 'cd "$1/bin" && ./-tool probe' sh "$root"
  run_case "$variant" symlink "$root/links/tool-link" probe
done

printf 'UNIT_02_MATRIX=%s\n' "$mode"
