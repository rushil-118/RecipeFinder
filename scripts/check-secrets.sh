#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

files="$(git ls-files 2>/dev/null || find . -type f -not -path './.git/*' -not -path './.venv/*')"
status=0

check() {
  hits="$(echo "$files" | grep -v -E '^scripts/check-secrets\.sh$' | xargs grep -n -I -i -E "$2" 2>/dev/null || true)"
  if [ -n "$hits" ]; then
    echo "Possible secret ($1):" >&2
    echo "$hits" | sed 's/^/  /' >&2
    status=1
  fi
}

check "private key"          '-----BEGIN [A-Z ]*PRIVATE KEY-----'
check "AWS access key id"    'AKIA[0-9A-Z]{16}'
check "GitHub token"         'gh[pousr]_[A-Za-z0-9]{36,}'
check "hard-coded credential" '(password|passwd|secret|api[_-]?key|token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{8,}["'"'"']'

[ "$status" = 0 ] && echo "check-secrets: no secrets found"
exit "$status"
