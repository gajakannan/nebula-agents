#!/bin/sh
# check-lint.sh — Run linter and formatter checks for the project.
#
# Usage:
#   ./check-lint.sh [--frontend-dir DIR] [--strict]
#
# Defaults:
#   --frontend-dir  experience
#   --strict        off (missing frontend/tooling is skipped)
#
# What it checks:
#   Frontend: ESLint (npm run lint) + Prettier format check (npm run format -- --check)
#   Backend:  No linter configured yet — see NOTE below.
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed
#   2  Lint tooling not found (package.json or scripts missing)
#
# NOTE (backend):
#   No backend linter is specified in the current project conventions.
#   When one is adopted, add its invocation in the "backend checks" section below.

FRONTEND_DIR="experience"
STRICT=0
FAILED=0

# --- parse arguments ---
while [ $# -gt 0 ]; do
  case "$1" in
    --frontend-dir)  FRONTEND_DIR="$2"; shift 2 ;;
    --strict)        STRICT=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--frontend-dir DIR] [--strict]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
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
}

# --- helper: run a named check, capture exit code ---
run_check() {
  label="$1"
  shift
  echo "--- ${label} ---"
  "$@"
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "FAIL: ${label} (exit ${rc})"
    FAILED=1
  else
    echo "OK: ${label}"
  fi
}

# =====================================================================
# Frontend checks
# =====================================================================
PKG="${FRONTEND_DIR}/package.json"

if [ ! -d "$FRONTEND_DIR" ]; then
  skip_or_fail "frontend directory not found at '${FRONTEND_DIR}'"
elif [ ! -f "$PKG" ]; then
  skip_or_fail "package.json not found at '${PKG}'"
else
  # Verify the expected scripts exist before running them.
  HAS_LINT=$(grep -Eq '"lint"[[:space:]]*:' "$PKG" && echo yes || echo no)
  HAS_FORMAT=$(grep -Eq '"format"[[:space:]]*:' "$PKG" && echo yes || echo no)

  if [ "$HAS_LINT" = "yes" ] && [ "$HAS_FORMAT" = "yes" ]; then
    cd "$FRONTEND_DIR" || exit 1
    run_check "ESLint" npm run lint
    run_check "Prettier (format check)" npm run format -- --check
    cd - >/dev/null
  else
    if [ "$HAS_LINT" = "yes" ]; then
      cd "$FRONTEND_DIR" || exit 1
      run_check "ESLint" npm run lint
      cd - >/dev/null
    else
      if [ "$STRICT" -eq 1 ]; then
        echo "ERROR: no 'lint' script in ${PKG}" >&2
        exit 2
      fi
      echo "SKIP (frontend lint): no 'lint' script in package.json"
    fi

    if [ "$HAS_FORMAT" = "yes" ]; then
      cd "$FRONTEND_DIR" || exit 1
      run_check "Prettier (format check)" npm run format -- --check
      cd - >/dev/null
    else
      if [ "$STRICT" -eq 1 ]; then
        echo "ERROR: no 'format' script in ${PKG}" >&2
        exit 2
      fi
      echo "SKIP (frontend format): no 'format' script in package.json"
    fi
  fi
fi

# =====================================================================
# Backend checks
# =====================================================================
echo "--- Backend linter ---"
echo "SKIP: no backend linter configured. Add one here when the project adopts one."

# =====================================================================
# Summary
# =====================================================================
echo ""
if [ $FAILED -eq 0 ]; then
  echo "All lint checks passed."
  exit 0
else
  echo "One or more lint checks FAILED. See output above."
  exit 1
fi
