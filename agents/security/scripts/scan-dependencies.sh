#!/bin/sh
# scan-dependencies.sh -- Scan dependency vulnerabilities by layer.
#
# Usage:
#   sh scan-dependencies.sh [options]
#
# Options:
#   --frontend-dir DIR    Frontend directory (default: experience)
#   --backend-dir DIR     Backend directory (default: engine)
#   --ai-dir DIR          AI directory (default: neuron)
#   --npm-level LEVEL     npm/pnpm/yarn audit level (default: high)
#   --skip-frontend       Skip frontend dependency scan
#   --skip-backend        Skip backend dependency scan
#   --skip-ai             Skip AI dependency scan
#   -h, --help            Show help
#
# Env overrides:
#   FRONTEND_DEP_SCAN_CMD  Custom frontend scan executable
#   BACKEND_DEP_SCAN_CMD   Custom backend scan executable
#   AI_DEP_SCAN_CMD        Custom AI scan executable
#
# Exit codes:
#   0  All executed scans passed
#   1  Vulnerabilities or scan failures detected
#   2  Usage/setup error or no scan executed

FRONTEND_DIR="${FRONTEND_DIR:-experience}"
BACKEND_DIR="${BACKEND_DIR:-engine}"
AI_DIR="${AI_DIR:-neuron}"
NPM_LEVEL="${NPM_LEVEL:-high}"

RUN_FRONTEND=1
RUN_BACKEND=1
RUN_AI=1

FAILED=0
RAN_ANY=0

print_usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --frontend-dir DIR    Frontend directory (default: experience)
  --backend-dir DIR     Backend directory (default: engine)
  --ai-dir DIR          AI directory (default: neuron)
  --npm-level LEVEL     npm/pnpm/yarn audit level (default: high)
  --skip-frontend       Skip frontend dependency scan
  --skip-backend        Skip backend dependency scan
  --skip-ai             Skip AI dependency scan
  -h, --help            Show help
EOF
}

has_backend_manifest() {
  find "$1" -maxdepth 5 -type f \( -name '*.sln' -o -name '*.csproj' \) -print -quit | grep -q .
}

has_ai_manifest() {
  dir="$1"
  if [ -f "${dir}/pyproject.toml" ] || [ -f "${dir}/setup.py" ] || [ -f "${dir}/requirements.txt" ]; then
    return 0
  fi
  find "$dir" -maxdepth 3 -type f -name 'requirements*.txt' -print -quit | grep -q .
}

run_frontend_scan() {
  if [ ! -d "$FRONTEND_DIR" ]; then
    echo "SKIP (frontend): directory not found (${FRONTEND_DIR})"
    return 0
  fi

  if [ ! -f "${FRONTEND_DIR}/package.json" ]; then
    echo "SKIP (frontend): package.json not found (${FRONTEND_DIR})"
    return 0
  fi

  RAN_ANY=1

  if [ -n "${FRONTEND_DEP_SCAN_CMD:-}" ]; then
    echo "Running frontend dependency scan via FRONTEND_DEP_SCAN_CMD."
    (cd "$FRONTEND_DIR" || exit 2; "$FRONTEND_DEP_SCAN_CMD")
    return $?
  fi

  if [ -f "${FRONTEND_DIR}/pnpm-lock.yaml" ] && command -v pnpm >/dev/null 2>&1; then
    echo "Running pnpm audit (level: ${NPM_LEVEL})."
    (cd "$FRONTEND_DIR" || exit 2; pnpm audit --audit-level "$NPM_LEVEL")
    return $?
  fi

  if [ -f "${FRONTEND_DIR}/yarn.lock" ] && command -v yarn >/dev/null 2>&1; then
    YARN_MAJOR=$(yarn --version 2>/dev/null | awk -F. '{print $1}')
    if [ "${YARN_MAJOR:-0}" -ge 2 ]; then
      echo "Running yarn npm audit (severity: ${NPM_LEVEL})."
      (cd "$FRONTEND_DIR" || exit 2; yarn npm audit --severity "$NPM_LEVEL")
    else
      echo "Running yarn audit (level: ${NPM_LEVEL})."
      (cd "$FRONTEND_DIR" || exit 2; yarn audit --level "$NPM_LEVEL")
    fi
    return $?
  fi

  if command -v npm >/dev/null 2>&1; then
    echo "Running npm audit (level: ${NPM_LEVEL})."
    (cd "$FRONTEND_DIR" || exit 2; npm audit --audit-level "$NPM_LEVEL")
    return $?
  fi

  echo "FAIL (frontend): no supported package manager found (pnpm/yarn/npm)." >&2
  return 2
}

run_backend_scan() {
  if [ ! -d "$BACKEND_DIR" ]; then
    echo "SKIP (backend): directory not found (${BACKEND_DIR})"
    return 0
  fi

  if ! has_backend_manifest "$BACKEND_DIR"; then
    echo "SKIP (backend): no .sln/.csproj found."
    return 0
  fi

  RAN_ANY=1

  if [ -n "${BACKEND_DEP_SCAN_CMD:-}" ]; then
    echo "Running backend dependency scan via BACKEND_DEP_SCAN_CMD."
    (cd "$BACKEND_DIR" || exit 2; "$BACKEND_DEP_SCAN_CMD")
    return $?
  fi

  if ! command -v dotnet >/dev/null 2>&1; then
    echo "FAIL (backend): dotnet not found in PATH." >&2
    return 2
  fi

  DOTNET_TARGET=$(find "$BACKEND_DIR" -maxdepth 3 -type f -name '*.sln' | head -n 1)
  if [ -z "$DOTNET_TARGET" ]; then
    DOTNET_TARGET=$(find "$BACKEND_DIR" -maxdepth 5 -type f -name '*.csproj' | head -n 1)
  fi

  if [ -z "$DOTNET_TARGET" ]; then
    echo "SKIP (backend): no target found for dotnet list package."
    return 0
  fi

  echo "Running dotnet dependency vulnerability scan on ${DOTNET_TARGET}."
  TMP_OUT=$(mktemp)
  dotnet list "$DOTNET_TARGET" package --vulnerable --include-transitive --format json >"$TMP_OUT" 2>&1
  rc=$?
  cat "$TMP_OUT"

  if [ $rc -ne 0 ]; then
    rm -f "$TMP_OUT"
    return $rc
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "FAIL (backend): python3 not found; unable to parse dotnet JSON output." >&2
    rm -f "$TMP_OUT"
    return 2
  fi

  python3 - "$TMP_OUT" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        data = json.load(fh)
except Exception:
    sys.exit(2)

def count_vulns(node):
    if isinstance(node, dict):
        total = 0
        for key, value in node.items():
            if key == "vulnerabilities" and isinstance(value, list):
                total += len(value)
            else:
                total += count_vulns(value)
        return total
    if isinstance(node, list):
        return sum(count_vulns(item) for item in node)
    return 0

count = count_vulns(data)
print(count)
sys.exit(1 if count > 0 else 0)
PY
  parse_rc=$?
  if [ $parse_rc -eq 1 ]; then
    rm -f "$TMP_OUT"
    echo "Vulnerable backend packages detected."
    return 1
  elif [ $parse_rc -ne 0 ]; then
    rm -f "$TMP_OUT"
    echo "FAIL (backend): unable to parse dotnet vulnerability output." >&2
    return 2
  fi

  rm -f "$TMP_OUT"
  echo "No vulnerable backend packages reported."
  return 0
}

run_ai_scan() {
  if [ ! -d "$AI_DIR" ]; then
    echo "SKIP (ai): directory not found (${AI_DIR})"
    return 0
  fi

  if ! has_ai_manifest "$AI_DIR"; then
    echo "SKIP (ai): no Python dependency manifest found."
    return 0
  fi

  RAN_ANY=1

  if [ -n "${AI_DEP_SCAN_CMD:-}" ]; then
    echo "Running AI dependency scan via AI_DEP_SCAN_CMD."
    (cd "$AI_DIR" || exit 2; "$AI_DEP_SCAN_CMD")
    return $?
  fi

  PIP_AUDIT_MODE=""
  if command -v pip-audit >/dev/null 2>&1; then
    PIP_AUDIT_MODE="bin"
  elif command -v python3 >/dev/null 2>&1 && python3 -c "import pip_audit" >/dev/null 2>&1; then
    PIP_AUDIT_MODE="py3"
  elif command -v python >/dev/null 2>&1 && python -c "import pip_audit" >/dev/null 2>&1; then
    PIP_AUDIT_MODE="py"
  else
    echo "FAIL (ai): pip-audit not found." >&2
    return 2
  fi

  run_pip_audit() {
    case "$PIP_AUDIT_MODE" in
      bin) pip-audit "$@" ;;
      py3) python3 -m pip_audit "$@" ;;
      py)  python -m pip_audit "$@" ;;
    esac
  }

  REQ_FILES=$(find "$AI_DIR" -maxdepth 3 -type f -name 'requirements*.txt' | sort)
  if [ -n "$REQ_FILES" ]; then
    rc=0
    echo "$REQ_FILES" | while IFS= read -r req; do
      [ -z "$req" ] && continue
      echo "Running pip-audit for ${req}."
      run_pip_audit -r "$req" || rc=1
      if [ $rc -ne 0 ]; then
        exit 1
      fi
    done
    return $?
  fi

  echo "Running pip-audit using current environment in ${AI_DIR}."
  (cd "$AI_DIR" || exit 2; run_pip_audit)
  return $?
}

while [ $# -gt 0 ]; do
  case "$1" in
    --frontend-dir)
      FRONTEND_DIR="$2"
      shift 2
      ;;
    --backend-dir)
      BACKEND_DIR="$2"
      shift 2
      ;;
    --ai-dir)
      AI_DIR="$2"
      shift 2
      ;;
    --npm-level)
      NPM_LEVEL="$2"
      shift 2
      ;;
    --skip-frontend)
      RUN_FRONTEND=0
      shift
      ;;
    --skip-backend)
      RUN_BACKEND=0
      shift
      ;;
    --skip-ai)
      RUN_AI=0
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

echo "=== Dependency Vulnerability Scan ==="

if [ "$RUN_FRONTEND" -eq 1 ]; then
  echo "--- Frontend ---"
  run_frontend_scan
  rc=$?
  if [ $rc -ne 0 ]; then
    FAILED=1
    echo "FAIL (frontend): dependency scan failed (exit ${rc})."
  else
    echo "OK (frontend): dependency scan passed or skipped."
  fi
fi

if [ "$RUN_BACKEND" -eq 1 ]; then
  echo "--- Backend ---"
  run_backend_scan
  rc=$?
  if [ $rc -ne 0 ]; then
    FAILED=1
    echo "FAIL (backend): dependency scan failed (exit ${rc})."
  else
    echo "OK (backend): dependency scan passed or skipped."
  fi
fi

if [ "$RUN_AI" -eq 1 ]; then
  echo "--- AI ---"
  run_ai_scan
  rc=$?
  if [ $rc -ne 0 ]; then
    FAILED=1
    echo "FAIL (ai): dependency scan failed (exit ${rc})."
  else
    echo "OK (ai): dependency scan passed or skipped."
  fi
fi

if [ "$RAN_ANY" -eq 0 ]; then
  echo "No dependency scans were executed."
  exit 2
fi

if [ "$FAILED" -ne 0 ]; then
  echo "Dependency scan completed with failures."
  exit 1
fi

echo "Dependency scan completed successfully."
exit 0
