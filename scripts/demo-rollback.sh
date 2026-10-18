#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
NS="${NAMESPACE:-recipe-finder}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
SHA="$(git rev-parse HEAD)"
OUT="${GITHUB_STEP_SUMMARY:-/dev/null}"
say() { echo "$*"; echo "$*" >> "$OUT"; }

smoke() {
  kubectl -n "$NS" port-forward svc/recipe-finder "$LOCAL_PORT:80" >/dev/null 2>&1 & local pf=$!
  sleep 3; bash scripts/smoke.sh "http://localhost:$LOCAL_PORT" "${SHA:0:12}" >/dev/null; local rc=$?
  kill $pf 2>/dev/null; return $rc
}

say "### Bad release demo"
say "- before: $(helm -n "$NS" history recipe-finder | tail -1)"

say "- upgrading to an image tag that does not exist..."
helm -n "$NS" upgrade recipe-finder charts/recipe-finder --reuse-values \
  --set image.tag=does-not-exist --set image.pullPolicy=Always --wait --timeout 45s \
  && { say "FAIL: bad release unexpectedly succeeded"; exit 1; }
say "- upgrade failed, as expected. Pods now:"
kubectl -n "$NS" get pods | tee -a "$OUT"

smoke && say "- the app kept serving during the failed rollout: **PASS**" \
      || { say "FAIL: app stopped serving"; exit 1; }

helm -n "$NS" rollback recipe-finder
kubectl -n "$NS" rollout status deployment/recipe-finder --timeout=120s
smoke && say "- after \`helm rollback\` the original version is serving: **PASS**" \
      || { say "FAIL: not healthy after rollback"; exit 1; }
helm -n "$NS" history recipe-finder | tail -4 | tee -a "$OUT"