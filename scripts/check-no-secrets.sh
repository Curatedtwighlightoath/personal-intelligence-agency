#!/usr/bin/env bash
#
# check-no-secrets.sh — scan the repo for API keys and other high-value
# credentials. One script, three modes:
#
#   check-no-secrets.sh            # scan the working tree (git-tracked files)
#   check-no-secrets.sh --staged   # scan the staged diff (pre-commit hook)
#   check-no-secrets.sh --range A..B   # scan the diff over a range (CI)
#
# Exits 1 on any finding so the offending commit or push is blocked. The
# pattern set lives here and nowhere else — the pre-commit hook and the
# GitHub workflow both exec this script.

set -euo pipefail

# Named patterns (POSIX ERE). One combined alternation is used for fast
# scanning; individual patterns are used only to label findings.
PATTERNS=(
  'anthropic|sk-ant-api[0-9]+-[A-Za-z0-9_-]{20,}'
  'openai-proj|sk-proj-[A-Za-z0-9_-]{20,}'
  'openai-legacy|sk-[A-Za-z0-9]{40,}'
  'github-pat|ghp_[A-Za-z0-9]{36,}'
  'github-fine|github_pat_[A-Za-z0-9_]{60,}'
  'google-api|AIza[0-9A-Za-z_-]{35}'
  'slack|xox[aboprs]-[A-Za-z0-9-]{10,}'
)

COMBINED=""
for entry in "${PATTERNS[@]}"; do
  r="${entry#*|}"
  if [[ -z "$COMBINED" ]]; then
    COMBINED="$r"
  else
    COMBINED="$COMBINED|$r"
  fi
done

ENV_PATH_RE='(^|/)\.env($|\.)'
ENV_ALLOWLIST='(^|/)\.env\.example$'
SELF_PATH='scripts/check-no-secrets.sh'

mode="tree"
range=""
if [[ ${1:-} == "--staged" ]]; then
  mode="staged"
elif [[ ${1:-} == "--range" ]]; then
  mode="range"
  range="${2:-}"
  if [[ -z "$range" ]]; then
    echo "check-no-secrets: --range requires A..B" >&2
    exit 2
  fi
fi

found=0

match_line() {
  # $1 = content; echoes the name of the first matching pattern, or nothing.
  local content="$1"
  for entry in "${PATTERNS[@]}"; do
    local name="${entry%%|*}"
    local r="${entry#*|}"
    if grep -Eq -- "$r" <<< "$content"; then
      echo "$name"
      return 0
    fi
  done
}

check_forbidden_path() {
  # $1 = path
  local p="$1"
  [[ -z "$p" ]] && return 0
  if [[ "$p" =~ $ENV_PATH_RE ]] && ! [[ "$p" =~ $ENV_ALLOWLIST ]]; then
    echo "SECRET FOUND: $p: forbidden path (.env* files must not be committed)" >&2
    found=1
  fi
}

scan_diff_plus_lines() {
  # Reads a unified diff on stdin. For each '+' (added) line, check it
  # against the combined regex; label with the specific pattern name.
  local current_file="" lineno=0
  while IFS= read -r line; do
    if [[ "$line" =~ ^\+\+\+\ b/(.*)$ ]]; then
      current_file="${BASH_REMATCH[1]}"
      lineno=0
      continue
    fi
    if [[ "$line" =~ ^@@\ -[0-9,]+\ \+([0-9]+)(,[0-9]+)?\ @@ ]]; then
      lineno=$((${BASH_REMATCH[1]} - 1))
      continue
    fi
    case "$line" in
      +++*) continue ;;
      ---*) continue ;;
      -*)   continue ;;
      +*)
        lineno=$((lineno + 1))
        # Exempt this script's own patterns-as-source from matching itself.
        if [[ "$current_file" == "$SELF_PATH" ]]; then
          continue
        fi
        local content="${line:1}"
        if grep -Eq -- "$COMBINED" <<< "$content"; then
          local name
          name="$(match_line "$content")"
          echo "SECRET FOUND: $current_file:$lineno: pattern=${name:-unknown}" >&2
          found=1
        fi
        ;;
      *)
        # context line (shouldn't exist at -U0 but harmless)
        lineno=$((lineno + 1))
        ;;
    esac
  done
}

case "$mode" in
  tree)
    # Fast path: one git grep against every tracked text file, excluding
    # this script. Then enumerate hits and label by pattern.
    hits=$(git grep -InE -- "$COMBINED" -- ':!scripts/check-no-secrets.sh' || true)
    if [[ -n "$hits" ]]; then
      while IFS= read -r hit; do
        # format: path:line:content
        path="${hit%%:*}"; rest="${hit#*:}"
        lineno="${rest%%:*}"; content="${rest#*:}"
        name="$(match_line "$content")"
        echo "SECRET FOUND: $path:$lineno: pattern=${name:-unknown}" >&2
        found=1
      done <<< "$hits"
    fi
    # Forbidden .env* paths among tracked files.
    while IFS= read -r p; do
      check_forbidden_path "$p"
    done < <(git ls-files | grep -E -- "$ENV_PATH_RE" || true)
    ;;

  staged)
    while IFS= read -r p; do
      check_forbidden_path "$p"
    done < <(git diff --cached --name-only --diff-filter=AM)
    scan_diff_plus_lines < <(git diff --cached -U0 --no-color)
    ;;

  range)
    if ! git rev-parse --verify "${range%%..*}" >/dev/null 2>&1 || \
       ! git rev-parse --verify "${range##*..}" >/dev/null 2>&1; then
      echo "check-no-secrets: range $range not resolvable, falling back to tree scan" >&2
      exec "$0"
    fi
    while IFS= read -r p; do
      check_forbidden_path "$p"
    done < <(git diff --name-only --diff-filter=AM "$range")
    scan_diff_plus_lines < <(git diff -U0 --no-color "$range")
    ;;
esac

if [[ $found -ne 0 ]]; then
  cat >&2 <<'EOF'

A secret or forbidden path was detected. This commit was blocked.

If this is a false positive:
  - Move the literal out of the tracked file (use an env var / .env.example).
  - Or, as a last resort: git commit --no-verify (strongly discouraged).

If it's a real key: rotate it now at the provider console, then remove it
from the working tree. The pre-commit hook is enabled via:
  git config core.hooksPath .githooks
EOF
  exit 1
fi

echo "check-no-secrets: clean ($mode)"
