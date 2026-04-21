#!/bin/sh
# run-tests.sh — Run frontend tests with sensible defaults.
#
# Usage:
#   sh run-tests.sh [--frontend-dir DIR] [--strict] [-- <test-runner-args>]
#
# Examples:
#   sh run-tests.sh
#   sh run-tests.sh -- --run
#   FRONTEND_TEST_CMD="npm run test:coverage" sh run-tests.sh
#
# Behavior:
# - If FRONTEND_TEST_CMD is set, run that command (and forward args after --).
# - Otherwise auto-detect package manager (pnpm/yarn/npm) and run test script.
# - Missing frontend setup is skipped unless --strict is set.
# - Exits non-zero on test failures.

FRONTEND_DIR="${FRONTEND_DIR:-experience}"
STRICT=0

print_usage() {
  echo "Usage: $0 [--frontend-dir DIR] [--strict] [-- <test-runner-args>]"
}

# Parse script options only; remaining args are forwarded.
while [ $# -gt 0 ]; do
  case "$1" in
    --frontend-dir)
      FRONTEND_DIR="$2"
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
    --)
      shift
      break
      ;;
    *)
      break
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

if [ ! -d "$FRONTEND_DIR" ]; then
  skip_or_fail "frontend directory not found: $FRONTEND_DIR"
fi

PKG="${FRONTEND_DIR}/package.json"
if [ ! -f "$PKG" ]; then
  skip_or_fail "package.json not found: $PKG"
fi

if [ -n "${FRONTEND_TEST_CMD:-}" ]; then
  echo "Running frontend tests via FRONTEND_TEST_CMD in $FRONTEND_DIR"
  (
    cd "$FRONTEND_DIR" || exit 2
    sh -c "$FRONTEND_TEST_CMD \"\$@\"" sh "$@"
  )
  exit $?
fi

if grep -Eq '"test"[[:space:]]*:' "$PKG"; then
  HAS_TEST_SCRIPT=1
else
  HAS_TEST_SCRIPT=0
fi

if [ "$HAS_TEST_SCRIPT" -ne 1 ]; then
  if [ "$STRICT" -eq 1 ]; then
    echo "ERROR: no \"test\" script found in $PKG." >&2
    echo "Set FRONTEND_TEST_CMD to run a custom test command." >&2
    exit 2
  fi
  echo "SKIP: no \"test\" script found in $PKG."
  echo "Set FRONTEND_TEST_CMD or run with --strict once tests are expected."
  exit 0
fi

if [ -f "${FRONTEND_DIR}/pnpm-lock.yaml" ] && command -v pnpm >/dev/null 2>&1; then
  RUNNER="pnpm"
elif [ -f "${FRONTEND_DIR}/yarn.lock" ] && command -v yarn >/dev/null 2>&1; then
  RUNNER="yarn"
elif command -v npm >/dev/null 2>&1; then
  RUNNER="npm"
else
  skip_or_fail "no supported package manager found (pnpm, yarn, npm)"
fi

echo "Running frontend tests with ${RUNNER} in $FRONTEND_DIR"
(
  cd "$FRONTEND_DIR" || exit 2
  case "$RUNNER" in
    pnpm)
      pnpm test "$@"
      ;;
    yarn)
      yarn test "$@"
      ;;
    npm)
      if [ $# -gt 0 ]; then
        npm test -- "$@"
      else
        npm test
      fi
      ;;
  esac
)
exit $?
