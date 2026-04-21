#!/bin/sh
# check-pr-size.sh — Flag PRs that exceed a line-change threshold.
#
# Usage:
#   ./check-pr-size.sh [--base BRANCH] [--max LINES]
#
# Defaults:
#   --base  main
#   --max   500   (lines added)
#
# Exit codes:
#   0  PR is within the threshold (or no commits to compare)
#   1  PR exceeds the threshold

BASE="main"
MAX=500

# --- parse arguments ---
while [ $# -gt 0 ]; do
  case "$1" in
    --base)  BASE="$2"; shift 2 ;;
    --max)   MAX="$2";  shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--base BRANCH] [--max LINES]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# --- sanity checks ---
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository." >&2
  exit 1
fi

if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  echo "ERROR: base branch '$BASE' not found." >&2
  exit 1
fi

# --- count lines ---
# git diff --numstat outputs: added  removed  filename
# Binary files show '-' for counts; awk treats them as 0 via +0.
STATS=$(git diff --numstat "${BASE}..HEAD")

ADDED=$(echo "$STATS"   | awk '{sum += $1} END {print sum + 0}')
REMOVED=$(echo "$STATS" | awk '{sum += $2} END {print sum + 0}')
FILES=$(echo "$STATS"   | awk 'NF {n++} END {print n + 0}')

echo "PR size: ${FILES} file(s) changed, ${ADDED} insertion(s), ${REMOVED} deletion(s)"
echo "Threshold: max ${MAX} lines added (base: ${BASE})"

if [ "$ADDED" -gt "$MAX" ]; then
  echo ""
  echo "WARNING: PR exceeds the size threshold (${ADDED} > ${MAX} lines added)."
  echo "Consider splitting into smaller, reviewable chunks."
  exit 1
fi

echo "OK: within threshold."
exit 0
