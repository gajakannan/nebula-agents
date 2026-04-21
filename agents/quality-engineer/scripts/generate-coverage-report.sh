#!/bin/sh
# generate-coverage-report.sh -- Run coverage generation for project layers.
#
# Usage:
#   sh generate-coverage-report.sh [options]
#
# Options:
#   --frontend-dir DIR   Frontend directory (default: experience)
#   --backend-dir DIR    Backend directory (default: engine)
#   --ai-dir DIR         AI directory (default: neuron)
#   --min PCT            Minimum coverage percent for validation (default: 80)
#   --strict             Fail when no coverage jobs can run
#   --no-validate        Generate reports but skip threshold validation
#   --skip-frontend      Skip frontend coverage
#   --skip-backend       Skip backend coverage
#   --skip-ai            Skip AI coverage
#   -h, --help           Show help
#
# Env overrides:
#   FRONTEND_COVERAGE_CMD   Custom command run inside FRONTEND_DIR
#   BACKEND_COVERAGE_CMD    Custom command run inside BACKEND_DIR
#   AI_COVERAGE_CMD         Custom command run inside AI_DIR
#
# Notes:
# - Coverage validation uses validate-test-coverage.py in this folder.
# - This script runs each layer independently and prints a final summary.
# - Backend fallback prefers the XPlat collector when `coverlet.collector`
#   is referenced, and falls back to `coverlet.msbuild` for older repos.

FRONTEND_DIR="${FRONTEND_DIR:-experience}"
BACKEND_DIR="${BACKEND_DIR:-engine}"
AI_DIR="${AI_DIR:-neuron}"
MIN_COVERAGE="${MIN_COVERAGE:-80}"
STRICT=0
VALIDATE=1
RUN_FRONTEND=1
RUN_BACKEND=1
RUN_AI=1

FAILED=0
RAN_ANY=0

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VALIDATOR="${SCRIPT_DIR}/validate-test-coverage.py"

print_usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --frontend-dir DIR   Frontend directory (default: experience)
  --backend-dir DIR    Backend directory (default: engine)
  --ai-dir DIR         AI directory (default: neuron)
  --min PCT            Minimum coverage percent for validation (default: 80)
  --strict             Fail when no coverage jobs can run
  --no-validate        Generate reports but skip threshold validation
  --skip-frontend      Skip frontend coverage
  --skip-backend       Skip backend coverage
  --skip-ai            Skip AI coverage
  -h, --help           Show help
EOF
}

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  return 1
}

find_package_manager() {
  dir="$1"
  if [ -f "${dir}/pnpm-lock.yaml" ] && command -v pnpm >/dev/null 2>&1; then
    echo "pnpm"
    return 0
  fi
  if [ -f "${dir}/yarn.lock" ] && command -v yarn >/dev/null 2>&1; then
    echo "yarn"
    return 0
  fi
  if command -v npm >/dev/null 2>&1; then
    echo "npm"
    return 0
  fi
  return 1
}

make_temp_dir() {
  base_dir="$1"
  mkdir -p "$base_dir" || return 1

  if command -v mktemp >/dev/null 2>&1; then
    mktemp -d "${base_dir}/coverage.XXXXXX"
    return $?
  fi

  temp_dir="${base_dir}/coverage.$$.${RANDOM:-0}"
  mkdir -p "$temp_dir" || return 1
  printf '%s\n' "$temp_dir"
}

dir_has_pattern() {
  search_dir="$1"
  pattern="$2"

  if command -v rg >/dev/null 2>&1; then
    rg -q "$pattern" "$search_dir" -g '*.csproj' -g '*.props' -g '*.targets'
    return $?
  fi

  grep -R -E -q --include='*.csproj' --include='*.props' --include='*.targets' "$pattern" "$search_dir"
}

detect_backend_coverage_mode() {
  search_dir="$1"

  if dir_has_pattern "$search_dir" 'coverlet\.collector'; then
    echo "collector"
    return 0
  fi

  if dir_has_pattern "$search_dir" 'coverlet\.msbuild'; then
    echo "msbuild"
    return 0
  fi

  echo "none"
}

find_backend_test_target() {
  search_dir="$1"
  target=""

  target=$(find "$search_dir" -maxdepth 3 -name '*.sln' -print | head -n 1)
  if [ -n "$target" ]; then
    printf '%s\n' "$target"
    return 0
  fi

  target=$(find "$search_dir" -maxdepth 6 -name '*Tests*.csproj' -print | head -n 1)
  if [ -n "$target" ]; then
    printf '%s\n' "$target"
    return 0
  fi

  target=$(find "$search_dir" -maxdepth 6 -name '*.csproj' -print | head -n 1)
  if [ -n "$target" ]; then
    printf '%s\n' "$target"
    return 0
  fi

  return 1
}

run_validator() {
  label="$1"
  file="$2"

  if [ "$VALIDATE" -ne 1 ]; then
    return 0
  fi

  if [ ! -f "$VALIDATOR" ]; then
    echo "WARN: coverage validator not found: $VALIDATOR"
    return 0
  fi

  if [ -z "${PYTHON_BIN:-}" ]; then
    echo "WARN: python runtime not found; skipping validation for ${label}"
    return 0
  fi

  echo "Validating ${label} coverage from ${file} (min ${MIN_COVERAGE}%)"
  "$PYTHON_BIN" "$VALIDATOR" "$file" --min "$MIN_COVERAGE"
  rc=$?
  if [ $rc -ne 0 ]; then
    FAILED=1
  fi
  return $rc
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
    --min)
      MIN_COVERAGE="$2"
      shift 2
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    --no-validate)
      VALIDATE=0
      shift
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

if [ "$VALIDATE" -eq 1 ]; then
  PYTHON_BIN=$(find_python || true)
fi

echo "=== Coverage Generation ==="

if [ "$RUN_FRONTEND" -eq 1 ]; then
  echo "--- Frontend (${FRONTEND_DIR}) ---"
  if [ ! -d "$FRONTEND_DIR" ]; then
    echo "SKIP: directory not found."
  elif [ ! -f "${FRONTEND_DIR}/package.json" ]; then
    echo "SKIP: package.json not found."
  else
    if [ -n "${FRONTEND_COVERAGE_CMD:-}" ]; then
      echo "Running custom frontend coverage command."
      (
        cd "$FRONTEND_DIR" || exit 2
        sh -c "$FRONTEND_COVERAGE_CMD"
      )
      rc=$?
      if [ $rc -ne 0 ]; then
        echo "FAIL: frontend coverage command failed (exit ${rc})"
        FAILED=1
      else
        RAN_ANY=1
      fi
    elif grep -Eq '"test:coverage"[[:space:]]*:' "${FRONTEND_DIR}/package.json" || grep -Eq '"coverage"[[:space:]]*:' "${FRONTEND_DIR}/package.json"; then
      PM=$(find_package_manager "$FRONTEND_DIR" || true)
      if [ -z "$PM" ]; then
        echo "FAIL: no supported package manager found (pnpm, yarn, npm)."
        FAILED=1
      else
        if grep -Eq '"test:coverage"[[:space:]]*:' "${FRONTEND_DIR}/package.json"; then
          FE_SCRIPT="test:coverage"
        else
          FE_SCRIPT="coverage"
        fi

        echo "Running ${PM} run ${FE_SCRIPT}"
        (
          cd "$FRONTEND_DIR" || exit 2
          case "$PM" in
            pnpm) pnpm run "$FE_SCRIPT" ;;
            yarn) yarn run "$FE_SCRIPT" ;;
            npm) npm run "$FE_SCRIPT" ;;
          esac
        )
        rc=$?
        if [ $rc -ne 0 ]; then
          echo "FAIL: frontend coverage command failed (exit ${rc})"
          FAILED=1
        else
          RAN_ANY=1
        fi
      fi
    else
      echo "SKIP: no coverage script found (expected \"test:coverage\" or \"coverage\")."
    fi

    FE_FILE=""
    if [ -f "${FRONTEND_DIR}/coverage/lcov.info" ]; then
      FE_FILE="${FRONTEND_DIR}/coverage/lcov.info"
    elif [ -f "${FRONTEND_DIR}/coverage/lcov-report/lcov.info" ]; then
      FE_FILE="${FRONTEND_DIR}/coverage/lcov-report/lcov.info"
    elif [ -f "${FRONTEND_DIR}/lcov.info" ]; then
      FE_FILE="${FRONTEND_DIR}/lcov.info"
    elif [ -f "${FRONTEND_DIR}/coverage.xml" ]; then
      FE_FILE="${FRONTEND_DIR}/coverage.xml"
    elif [ -f "${FRONTEND_DIR}/coverage/coverage.xml" ]; then
      FE_FILE="${FRONTEND_DIR}/coverage/coverage.xml"
    fi

    if [ -n "$FE_FILE" ]; then
      run_validator "frontend" "$FE_FILE" || true
    else
      echo "INFO: frontend coverage file not found after run."
    fi
  fi
fi

if [ "$RUN_BACKEND" -eq 1 ]; then
  echo "--- Backend (${BACKEND_DIR}) ---"
  BE_FILE=""
  if [ ! -d "$BACKEND_DIR" ]; then
    echo "SKIP: directory not found."
  else
    BE_TARGET=$(find_backend_test_target "$BACKEND_DIR" || true)
    HAS_DOTNET_INPUT=0
    if [ -n "$BE_TARGET" ]; then
      HAS_DOTNET_INPUT=1
    fi

    if [ -n "${BACKEND_COVERAGE_CMD:-}" ]; then
      echo "Running custom backend coverage command."
      (
        cd "$BACKEND_DIR" || exit 2
        sh -c "$BACKEND_COVERAGE_CMD"
      )
      rc=$?
      if [ $rc -ne 0 ]; then
        echo "FAIL: backend coverage command failed (exit ${rc})"
        FAILED=1
      else
        RAN_ANY=1
      fi
    elif [ "$HAS_DOTNET_INPUT" -eq 1 ] && command -v dotnet >/dev/null 2>&1; then
      BE_MODE=$(detect_backend_coverage_mode "$BACKEND_DIR")
      case "$BE_MODE" in
        collector)
          BE_RESULTS_DIR=$(make_temp_dir "${BACKEND_DIR}/TestResults")
          if [ -z "$BE_RESULTS_DIR" ]; then
            echo "FAIL: could not create backend coverage results directory."
            FAILED=1
          else
            echo "Running dotnet test with XPlat Code Coverage collector."
            dotnet test "$BE_TARGET" --collect:"XPlat Code Coverage" --results-directory "$BE_RESULTS_DIR" --disable-build-servers -m:1 -nodeReuse:false
            rc=$?
            if [ $rc -ne 0 ]; then
              echo "FAIL: backend coverage command failed (exit ${rc})"
              FAILED=1
            else
              RAN_ANY=1
              BE_FILE=$(find "$BE_RESULTS_DIR" -type f \( -name 'coverage.cobertura.xml' -o -name 'coverage.xml' -o -name 'cobertura.xml' \) -print | head -n 1)
            fi
          fi
          ;;
        msbuild)
          BE_RESULTS_DIR=$(make_temp_dir "${BACKEND_DIR}/coverage")
          if [ -z "$BE_RESULTS_DIR" ]; then
            echo "FAIL: could not create backend coverage output directory."
            FAILED=1
          else
            echo "Running dotnet test with coverlet.msbuild output."
            dotnet test "$BE_TARGET" /p:CollectCoverage=true /p:CoverletOutput="${BE_RESULTS_DIR}/" /p:CoverletOutputFormat=cobertura --disable-build-servers -m:1 -nodeReuse:false
            rc=$?
            if [ $rc -ne 0 ]; then
              echo "FAIL: backend coverage command failed (exit ${rc})"
              FAILED=1
            else
              RAN_ANY=1
              BE_FILE=$(find "$BE_RESULTS_DIR" -type f \( -name 'coverage.cobertura.xml' -o -name 'coverage.xml' -o -name 'cobertura.xml' \) -print | head -n 1)
            fi
          fi
          ;;
        *)
          echo "SKIP: no supported backend coverage package found (expected coverlet.collector or coverlet.msbuild)."
          echo "      Set BACKEND_COVERAGE_CMD to use a project-specific coverage command."
          ;;
      esac
    else
      if [ "$HAS_DOTNET_INPUT" -ne 1 ]; then
        echo "SKIP: no .sln/.csproj found."
      else
        echo "SKIP: dotnet not found in PATH."
      fi
    fi

    if [ -n "$BE_FILE" ]; then
      run_validator "backend" "$BE_FILE" || true
    else
      echo "INFO: backend coverage file not found after run."
    fi
  fi
fi

if [ "$RUN_AI" -eq 1 ]; then
  echo "--- AI (${AI_DIR}) ---"
  if [ ! -d "$AI_DIR" ]; then
    echo "SKIP: directory not found."
  else
    if [ -n "${AI_COVERAGE_CMD:-}" ]; then
      echo "Running custom AI coverage command."
      (
        cd "$AI_DIR" || exit 2
        sh -c "$AI_COVERAGE_CMD"
      )
      rc=$?
      if [ $rc -ne 0 ]; then
        echo "FAIL: AI coverage command failed (exit ${rc})"
        FAILED=1
      else
        RAN_ANY=1
      fi
    elif command -v pytest >/dev/null 2>&1; then
      echo "Running pytest coverage."
      (
        cd "$AI_DIR" || exit 2
        pytest --cov=. --cov-report=xml:coverage.xml
      )
      rc=$?
      if [ $rc -ne 0 ]; then
        echo "FAIL: AI coverage command failed (exit ${rc})"
        FAILED=1
      else
        RAN_ANY=1
      fi
    else
      echo "SKIP: pytest not found in PATH."
    fi

    AI_FILE=""
    if [ -f "${AI_DIR}/coverage.xml" ]; then
      AI_FILE="${AI_DIR}/coverage.xml"
    elif [ -f "${AI_DIR}/coverage/coverage.xml" ]; then
      AI_FILE="${AI_DIR}/coverage/coverage.xml"
    elif [ -f "${AI_DIR}/cobertura.xml" ]; then
      AI_FILE="${AI_DIR}/cobertura.xml"
    fi

    if [ -n "$AI_FILE" ]; then
      run_validator "AI" "$AI_FILE" || true
    else
      echo "INFO: AI coverage file not found after run."
    fi
  fi
fi

echo "=== Coverage Summary ==="
if [ "$RAN_ANY" -eq 1 ]; then
  echo "At least one coverage job ran."
else
  if [ "$FAILED" -ne 0 ]; then
    echo "Coverage generation failed before any coverage artifact was produced."
    exit 1
  fi
  if [ "$STRICT" -eq 1 ]; then
    echo "No coverage jobs ran. Check directories/tooling or pass custom commands."
    exit 2
  fi
  echo "SKIP: no coverage jobs ran. Use --strict when coverage must be present."
  exit 0
fi

if [ "$FAILED" -ne 0 ]; then
  echo "Coverage generation completed with failures."
  exit 1
fi

echo "Coverage generation completed successfully."
exit 0
