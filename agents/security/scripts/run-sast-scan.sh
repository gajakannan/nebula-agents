#!/bin/sh
# run-sast-scan.sh -- Run static application security testing (SAST).
#
# Usage:
#   sh run-sast-scan.sh [options] [-- <semgrep-extra-args>]
#
# Options:
#   --path DIR          Path to scan (default: .)
#   --config CONFIG     Semgrep config (default: auto)
#   --report-dir DIR    Output directory for SARIF report (default: security-reports)
#   --no-error          Do not fail build on findings (omit --error)
#   -h, --help          Show help
#
# Env override:
#   SAST_SCAN_CMD       Custom executable to run instead of semgrep
#
# Exit codes:
#   0  Scan passed (or findings allowed with --no-error)
#   1  Findings detected (default behavior)
#   2  Setup/usage/tooling error

TARGET_PATH="${TARGET_PATH:-.}"
SAST_CONFIG="${SAST_CONFIG:-auto}"
REPORT_DIR="${REPORT_DIR:-security-reports}"
ERROR_ON_FINDINGS=1

print_usage() {
  cat <<EOF
Usage: $0 [options] [-- <semgrep-extra-args>]

Options:
  --path DIR          Path to scan (default: .)
  --config CONFIG     Semgrep config (default: auto)
  --report-dir DIR    Output directory for SARIF report (default: security-reports)
  --no-error          Do not fail build on findings (omit --error)
  -h, --help          Show help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --path)
      TARGET_PATH="$2"
      shift 2
      ;;
    --config)
      SAST_CONFIG="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    --no-error)
      ERROR_ON_FINDINGS=0
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

if [ ! -d "$TARGET_PATH" ]; then
  echo "ERROR: scan path not found: $TARGET_PATH" >&2
  exit 2
fi

if [ -n "${SAST_SCAN_CMD:-}" ]; then
  echo "Running SAST via SAST_SCAN_CMD in $TARGET_PATH"
  (
    cd "$TARGET_PATH" || exit 2
    "$SAST_SCAN_CMD" "$@"
  )
  exit $?
fi

if ! command -v semgrep >/dev/null 2>&1; then
  echo "ERROR: semgrep not found in PATH." >&2
  echo "Install semgrep or set SAST_SCAN_CMD." >&2
  exit 2
fi

mkdir -p "$REPORT_DIR"
REPORT_DIR_ABS=$(CDPATH= cd -- "$REPORT_DIR" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
REPORT_PATH="${REPORT_DIR_ABS}/sast-semgrep-${STAMP}.sarif"

echo "Running semgrep SAST scan on ${TARGET_PATH} (config: ${SAST_CONFIG})"
echo "Report: ${REPORT_PATH}"

if [ "$ERROR_ON_FINDINGS" -eq 1 ]; then
  semgrep scan --config "$SAST_CONFIG" --error --sarif --output "$REPORT_PATH" "$TARGET_PATH" "$@"
else
  semgrep scan --config "$SAST_CONFIG" --sarif --output "$REPORT_PATH" "$TARGET_PATH" "$@"
fi

rc=$?
if [ $rc -eq 0 ]; then
  echo "SAST scan completed with no blocking findings."
  exit 0
fi

if [ $rc -eq 1 ]; then
  echo "SAST findings detected. Review report: ${REPORT_PATH}"
  exit 1
fi

echo "SAST scan failed (exit ${rc})."
exit 2
