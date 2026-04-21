#!/bin/sh
# run-dast-scan.sh -- Run dynamic application security testing (DAST) with OWASP ZAP baseline.
#
# Usage:
#   sh run-dast-scan.sh --target URL [options] [-- <zap-extra-args>]
#
# Options:
#   --target URL        Target base URL (required unless DAST_TARGET_URL/TARGET_URL set)
#   --max-minutes N     Spider time in minutes (default: 5)
#   --report-dir DIR    Output directory for report (default: security-reports)
#   --ignore-warn       Ignore warning-level findings (passes -I to ZAP)
#   -h, --help          Show help
#
# Env overrides:
#   DAST_TARGET_URL     Target URL if --target is omitted
#   DAST_SCAN_CMD       Custom executable to run instead of ZAP
#
# Exit codes:
#   0  No blocking issues found
#   1  Security findings detected
#   2  Setup/usage/tooling error

TARGET_URL="${TARGET_URL:-${DAST_TARGET_URL:-}}"
MAX_MINUTES="${MAX_MINUTES:-5}"
REPORT_DIR="${REPORT_DIR:-security-reports}"
IGNORE_WARN=0

print_usage() {
  cat <<EOF
Usage: $0 --target URL [options] [-- <zap-extra-args>]

Options:
  --target URL        Target base URL
  --max-minutes N     Spider time in minutes (default: 5)
  --report-dir DIR    Output directory for report (default: security-reports)
  --ignore-warn       Ignore warning-level findings
  -h, --help          Show help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      TARGET_URL="$2"
      shift 2
      ;;
    --max-minutes)
      MAX_MINUTES="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    --ignore-warn)
      IGNORE_WARN=1
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

if [ -z "$TARGET_URL" ]; then
  echo "ERROR: target URL is required (--target or DAST_TARGET_URL)." >&2
  exit 2
fi

if [ -n "${DAST_SCAN_CMD:-}" ]; then
  echo "Running DAST via DAST_SCAN_CMD against ${TARGET_URL}"
  export DAST_TARGET_URL="$TARGET_URL"
  "$DAST_SCAN_CMD" "$@"
  exit $?
fi

mkdir -p "$REPORT_DIR"
REPORT_DIR_ABS=$(CDPATH= cd -- "$REPORT_DIR" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
REPORT_NAME="dast-zap-baseline-${STAMP}.html"
REPORT_PATH="${REPORT_DIR_ABS}/${REPORT_NAME}"

RUNNER=""
if command -v zap-baseline.py >/dev/null 2>&1; then
  RUNNER="local"
elif command -v docker >/dev/null 2>&1; then
  RUNNER="docker"
else
  echo "ERROR: neither zap-baseline.py nor docker is available." >&2
  echo "Install OWASP ZAP CLI or docker, or set DAST_SCAN_CMD." >&2
  exit 2
fi

echo "Running DAST scan with OWASP ZAP baseline (${RUNNER})"
echo "Target: ${TARGET_URL}"
echo "Report: ${REPORT_PATH}"

if [ "$RUNNER" = "local" ]; then
  if [ "$IGNORE_WARN" -eq 1 ]; then
    zap-baseline.py -t "$TARGET_URL" -m "$MAX_MINUTES" -I -r "$REPORT_PATH" "$@"
  else
    zap-baseline.py -t "$TARGET_URL" -m "$MAX_MINUTES" -r "$REPORT_PATH" "$@"
  fi
else
  if [ "$IGNORE_WARN" -eq 1 ]; then
    docker run --rm -v "${REPORT_DIR_ABS}:/zap/wrk/:rw" owasp/zap2docker-stable \
      zap-baseline.py -t "$TARGET_URL" -m "$MAX_MINUTES" -I -r "$REPORT_NAME" "$@"
  else
    docker run --rm -v "${REPORT_DIR_ABS}:/zap/wrk/:rw" owasp/zap2docker-stable \
      zap-baseline.py -t "$TARGET_URL" -m "$MAX_MINUTES" -r "$REPORT_NAME" "$@"
  fi
fi

rc=$?
case "$rc" in
  0)
    echo "DAST scan completed with no blocking issues."
    exit 0
    ;;
  1|2)
    echo "DAST findings detected. Review report: ${REPORT_PATH}"
    exit 1
    ;;
  *)
    echo "DAST scan failed (exit ${rc})."
    exit 2
    ;;
esac
