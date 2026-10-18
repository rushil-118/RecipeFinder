#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER="${CLUSTER:-recipe-finder}"
NAMESPACE="${NAMESPACE:-recipe-finder}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
SHA="$(git rev-parse HEAD)"
TAG="${IMAGE_TAG:-${SHA:0:12}}"
IMAGE="recipe-finder:${TAG}"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  docker build --build-arg VERSION="$TAG" --build-arg GIT_SHA="$SHA" -t "$IMAGE" .
fi

kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER"
kubectl config use-context "kind-$CLUSTER" >/dev/null
kind load docker-image "$IMAGE" --name "$CLUSTER"

helm upgrade --install recipe-finder charts/recipe-finder \
  --namespace "$NAMESPACE" --create-namespace \
  --set image.repository=recipe-finder --set image.tag="$TAG" --set image.pullPolicy=Never \
  --atomic --wait --timeout 3m

kubectl -n "$NAMESPACE" rollout status deployment/recipe-finder --timeout=120s
kubectl -n "$NAMESPACE" get pods -o wide
kubectl -n "$NAMESPACE" get pods -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.status.containerStatuses[0].image}{"\n"}{end}'

kubectl -n "$NAMESPACE" port-forward svc/recipe-finder "$LOCAL_PORT:80" >/tmp/port-forward.log 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
sleep 3
bash scripts/smoke.sh "http://localhost:$LOCAL_PORT" "${SHA:0:12}"