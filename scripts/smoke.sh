#!/usr/bin/env bash
set -euo pipefail

BASE="${1:?usage: smoke.sh <base-url> [expected-commit]}"
EXPECTED="${2:-}"
OUT="${GITHUB_STEP_SUMMARY:-/dev/null}"

say() { echo "$*"; echo "$*" >> "$OUT"; }
fail() { echo "FAIL: $*" >&2; echo "FAIL: $*" >> "$OUT"; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

say "### Smoke test of $BASE"

for i in $(seq 1 30); do
  [ "$(code "$BASE/ready" || true)" = "200" ] && break
  [ "$i" = 30 ] && fail "/ready never returned 200"
  sleep 2
done
say "- ready: catalog loaded"

VERSION_JSON="$(curl -fs "$BASE/version")" || fail "/version request failed"
say "- /version: \`$VERSION_JSON\`"
if [ -n "$EXPECTED" ]; then
  echo "$VERSION_JSON" | grep -q "\"commit\":\"$EXPECTED" || fail "running commit does not match $EXPECTED"
  say "- running commit matches \`$EXPECTED\`"
fi

curl -fs "$BASE/recipes/cuisines" | grep -q '"Italian"' || fail "cuisines list is missing Italian"
curl -fs "$BASE/recipes/count?cuisine=Italian" | grep -q '"count":7' || fail "Italian count is not 7"
curl -fs "$BASE/recipes/names?cuisine=Thai" | grep -q 'Pad Thai' || fail "Thai names missing Pad Thai"
curl -fs "$BASE/recipes/quick?max_minutes=10&vegetarian=true" | grep -q 'Edamame' || fail "quick query missing Edamame"
say "- count, names and quick queries return the expected data"

[ "$(code "$BASE/recipes/count")" = "400" ] || fail "missing parameter was not rejected with 400"
say "- bad request rejected (400)"

NUTRITION="$(code "$BASE/recipes/calories?cuisine=Indian")"
case "$NUTRITION" in
  200) say "- calories query works (feature flag on)";;
  403) say "- calories query disabled by feature flag (403), as configured";;
  *)   fail "calories query returned $NUTRITION";;
esac

METRICS="$(curl -fs "$BASE/metrics")" || fail "/metrics request failed"
echo "$METRICS" | grep -q 'http_requests_total{method="GET",route="/recipes/count",status="200"}' \
  || fail "traffic not visible in /metrics"
echo "$METRICS" | grep -q '^recipes_loaded [1-9]' || fail "recipes_loaded is not positive"
echo "$METRICS" | grep -q '^build_info{' || fail "build_info missing"
say "- /metrics shows the traffic, recipes_loaded and build_info"
say "**PASS**"
