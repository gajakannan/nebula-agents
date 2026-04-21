#!/bin/sh
# check-test-coverage.sh — Delegate to Quality Engineer coverage validator.
#
# The authoritative coverage parser lives at:
#   agents/quality-engineer/scripts/validate-test-coverage.py
#
# It already handles lcov (.info) and Cobertura XML, supports --min threshold
# and --auto file discovery. Use that script directly instead of this one.
#
# Example:
#   python agents/quality-engineer/scripts/validate-test-coverage.py --min 80 --auto
#

set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
QE_SCRIPT="${SCRIPT_DIR}/../../quality-engineer/scripts/validate-test-coverage.py"

if [ ! -f "$QE_SCRIPT" ]; then
  echo "ERROR: coverage validator not found: $QE_SCRIPT" >&2
  exit 2
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: python runtime not found (python3/python)." >&2
  exit 2
fi

exec "$PYTHON_BIN" "$QE_SCRIPT" "$@"
