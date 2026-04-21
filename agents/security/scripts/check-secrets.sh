#!/bin/sh
# check-secrets.sh -- Scan for hardcoded secrets using gitleaks.
#
# Usage:
#   sh check-secrets.sh [options] [-- <gitleaks-extra-args>]
#
# Options:
#   --path DIR          Path to scan (default: .)
#   --mode MODE         Scan mode: auto|git|filesystem (default: auto)
#   --report-dir DIR    Output directory for SARIF report (default: security-reports)
#   --baseline FILE     Optional gitleaks baseline file
#   --no-redact         Disable redaction in output report
#   -h, --help          Show help
#
# Env override:
#   SECRET_SCAN_CMD     Custom executable to run instead of gitleaks
#
# Exit codes:
#   0  No secret leaks found
#   1  Secret leaks found
#   2  Setup/usage/tooling error

TARGET_PATH="${TARGET_PATH:-.}"
MODE="${MODE:-auto}"
REPORT_DIR="${REPORT_DIR:-security-reports}"
BASELINE_PATH="${BASELINE_PATH:-}"
REDACT=1

print_usage() {
  cat <<EOF
Usage: $0 [options] [-- <gitleaks-extra-args>]

Options:
  --path DIR          Path to scan (default: .)
  --mode MODE         Scan mode: auto|git|filesystem (default: auto)
  --report-dir DIR    Output directory for SARIF report (default: security-reports)
  --baseline FILE     Optional gitleaks baseline file
  --no-redact         Disable redaction in output report
  -h, --help          Show help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --path)
      TARGET_PATH="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    --baseline)
      BASELINE_PATH="$2"
      shift 2
      ;;
    --no-redact)
      REDACT=0
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

case "$MODE" in
  auto|git|filesystem) ;;
  *)
    echo "ERROR: invalid --mode value: $MODE" >&2
    print_usage >&2
    exit 2
    ;;
esac

if [ ! -d "$TARGET_PATH" ]; then
  echo "ERROR: scan path not found: $TARGET_PATH" >&2
  exit 2
fi

if [ -n "${SECRET_SCAN_CMD:-}" ]; then
  echo "Running secret scan via SECRET_SCAN_CMD in $TARGET_PATH"
  (
    cd "$TARGET_PATH" || exit 2
    "$SECRET_SCAN_CMD" "$@"
  )
  exit $?
fi

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "ERROR: gitleaks not found in PATH." >&2
  echo "Install gitleaks or set SECRET_SCAN_CMD." >&2
  exit 2
fi

if [ "$MODE" = "auto" ]; then
  # Prefer filesystem mode to include untracked working-tree content.
  MODE="filesystem"
fi

mkdir -p "$REPORT_DIR"
REPORT_DIR_ABS=$(CDPATH= cd -- "$REPORT_DIR" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
REPORT_PATH="${REPORT_DIR_ABS}/secrets-gitleaks-${STAMP}.sarif"

echo "Running gitleaks (${MODE} mode) on ${TARGET_PATH}"
echo "Report: ${REPORT_PATH}"

if [ "$MODE" = "git" ] && ! (cd "$TARGET_PATH" && git rev-parse --is-inside-work-tree >/dev/null 2>&1); then
  echo "ERROR: --mode git requires a git repository at $TARGET_PATH" >&2
  exit 2
fi

if [ "$MODE" = "git" ]; then
  if [ "$REDACT" -eq 1 ]; then
    if [ -n "$BASELINE_PATH" ]; then
      (cd "$TARGET_PATH" && gitleaks git --no-banner --redact --report-format sarif --report-path "$REPORT_PATH" --baseline-path "$BASELINE_PATH" "$@")
    else
      (cd "$TARGET_PATH" && gitleaks git --no-banner --redact --report-format sarif --report-path "$REPORT_PATH" "$@")
    fi
  else
    if [ -n "$BASELINE_PATH" ]; then
      (cd "$TARGET_PATH" && gitleaks git --no-banner --report-format sarif --report-path "$REPORT_PATH" --baseline-path "$BASELINE_PATH" "$@")
    else
      (cd "$TARGET_PATH" && gitleaks git --no-banner --report-format sarif --report-path "$REPORT_PATH" "$@")
    fi
  fi
else
  if [ "$REDACT" -eq 1 ]; then
    if [ -n "$BASELINE_PATH" ]; then
      gitleaks detect --source "$TARGET_PATH" --no-banner --redact --report-format sarif --report-path "$REPORT_PATH" --baseline-path "$BASELINE_PATH" "$@"
    else
      gitleaks detect --source "$TARGET_PATH" --no-banner --redact --report-format sarif --report-path "$REPORT_PATH" "$@"
    fi
  else
    if [ -n "$BASELINE_PATH" ]; then
      gitleaks detect --source "$TARGET_PATH" --no-banner --report-format sarif --report-path "$REPORT_PATH" --baseline-path "$BASELINE_PATH" "$@"
    else
      gitleaks detect --source "$TARGET_PATH" --no-banner --report-format sarif --report-path "$REPORT_PATH" "$@"
    fi
  fi
fi

rc=$?
if [ $rc -eq 0 ]; then
  echo "No secret leaks found."
  exit 0
fi

if [ $rc -eq 1 ]; then
  echo "Secret leaks detected. Review report: ${REPORT_PATH}"
  exit 1
fi

echo "Secret scan failed (exit ${rc})."
exit 2
