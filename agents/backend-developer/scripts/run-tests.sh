#!/bin/sh
# run-tests.sh -- Run backend tests with sensible defaults.
#
# Usage:
#   sh run-tests.sh [--backend-dir DIR] [--strict]
#
# Behavior:
# - If BACKEND_TEST_CMD is set, run it.
# - Otherwise run `dotnet test` when a .sln/.csproj exists in BACKEND_DIR.
# - Missing backend setup is skipped unless --strict is set.
#
# Defaults:
#   --backend-dir engine

BACKEND_DIR="${BACKEND_DIR:-engine}"
STRICT=0

print_usage() {
  echo "Usage: $0 [--backend-dir DIR] [--strict]"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --backend-dir)
      BACKEND_DIR="$2"
      shift 2
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

skip_or_fail() {
  msg="$1"
  if [ "$STRICT" -eq 1 ]; then
    echo "ERROR: ${msg}" >&2
    exit 2
  fi
  echo "SKIP: ${msg}"
  exit 0
}

if [ ! -d "$BACKEND_DIR" ]; then
  skip_or_fail "backend directory not found: $BACKEND_DIR"
fi

if [ -n "${BACKEND_TEST_CMD:-}" ]; then
  echo "Running BACKEND_TEST_CMD in $BACKEND_DIR"
  (
    cd "$BACKEND_DIR" || exit 2
    sh -c "$BACKEND_TEST_CMD"
  )
  exit $?
fi

HAS_DOTNET_INPUT=0
if find "$BACKEND_DIR" -maxdepth 3 -name "*.sln" -print -quit | grep -q .; then
  HAS_DOTNET_INPUT=1
elif find "$BACKEND_DIR" -maxdepth 5 -name "*.csproj" -print -quit | grep -q .; then
  HAS_DOTNET_INPUT=1
fi

if [ "$HAS_DOTNET_INPUT" -ne 1 ]; then
  skip_or_fail "no .sln/.csproj found under ${BACKEND_DIR}"
fi

if ! command -v dotnet >/dev/null 2>&1; then
  skip_or_fail "dotnet runtime not found in PATH"
fi

echo "Running dotnet test in $BACKEND_DIR"
(
  cd "$BACKEND_DIR" || exit 2
  dotnet test
)
exit $?
