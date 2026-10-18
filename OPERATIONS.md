# Operating Recipe Finder

## What "healthy" means
A pod is healthy when `/ready` returns 200 (catalog loaded) and requests succeed quickly. The service is healthy when it meets its SLOs.

## SLOs
| SLI | Target | Measured by |
|---|---|---|
| Availability: requests not failing with 5xx | 99% over 30 days | `recipe_finder:success_ratio:rate5m` |
| Latency: p95 request duration | < 100 ms | `recipe_finder:latency_p95:5m` |

4xx responses (bad parameters, unknown cuisine, a disabled feature) are client or configuration outcomes and do not count against availability.
The error budget is 1% of requests, roughly 7 hours of complete failure per 30 days.

## Signals
| Signal | Source | Use |
|---|---|---|
| Metrics | `GET /metrics` | `http_requests_total{method,route,status}`, `http_request_duration_seconds`, `recipes_loaded`, `feature_enabled`, `build_info` |
| Logs | stdout, one JSON line per event | `ts, level, msg, method, route, status, duration_ms, request_id, trace_id` |
| Correlation | `X-Request-Id` header (generated if absent, echoed back) and the trace ID from a W3C `traceparent` header | follow one request through the logs |
| Version | `GET /version`, `build_info`, pod label `app.kubernetes.io/version` | what exactly is running |

Probe and scrape requests are only logged when they fail. Route labels are patterns (`/recipes/count`, or `unmatched`), never raw paths, so the number of metric series stays bounded (a test checks this).

## Alerts and first responses
Defined in `monitoring/prometheus-rules.yaml`; each alert has an `action` annotation.
| Alert | Meaning | First response |
|---|---|---|
| RecipeFinderHighErrorRate | >5% 5xx for 5m | Recent deploy? `helm rollback recipe-finder`. Else read logs for `"status": 5xx` |
| RecipeFinderHighLatency | p95 >100ms for 10m | CPU throttling; raise CPU limit or replicas |
| RecipeFinderPodNotScraped | not scraped 2m | `kubectl describe pod`; probe failures, restarts |
| RecipeFinderCatalogEmpty | `recipes_loaded == 0` | Data file in the image; pod logs |
| RecipeFinderMixedVersions | >1 version for 15m | Stuck rollout; consider `helm rollback` |

To see these in a cluster, install kube-prometheus-stack and load the rules file as a PrometheusRule.
Without Prometheus: `curl localhost:8080/metrics` and `kubectl logs -l app.kubernetes.io/name=recipe-finder`.

## Verifying recovery
(1) `kubectl -n recipe-finder rollout status deployment/recipe-finder`, (2) `bash scripts/smoke.sh <url> <expected-commit>` (right version, real queries work), (3) the success-ratio SLI is back above target.

## Worked example: bad release (what `demo-rollback.sh` shows)
- **Symptom:** `helm upgrade` times out; the new pod is `ImagePullBackOff`.
- **Hypothesis:** the image tag does not exist.
- **Evidence:** `kubectl describe pod` shows the failed pull; the two old pods are still `Ready`; smoke test still passes.
- **Change:** `helm rollback recipe-finder`.
- **Verification:** `helm history` shows the rollback revision; the smoke test confirms the original commit is serving.

## Worked example: liveness failure
- **Symptom:** pods restart repeatedly (`RESTARTS` climbing) after `failHealth=true`.
- **Evidence:** `kubectl describe pod` shows `Liveness probe failed: HTTP probe failed with statuscode: 500`.
- **Change:** set `failHealth=false` with `helm upgrade --reuse-values`.
- **Verification:** pods stop restarting, `/health` returns 200, smoke test passes.

## Troubleshooting quick reference
| Symptom | Likely cause | First commands |
|---|---|---|
| Pending | not enough CPU/memory for the requests | `kubectl describe pod` (Events), `kubectl top nodes` |
| CrashLoopBackOff | bad CSV, OOM, failing liveness | `kubectl logs <pod> --previous`, `describe pod` (exit code) |
| ImagePullBackOff | wrong tag | `describe pod` |
| Running but 0/1 Ready | readiness failing (`/ready` 503) | `describe pod`, `exec` then `curl localhost:8080/ready` |
| Service unreachable | selector/labels mismatch, no ready pods | `kubectl get endpoints recipe-finder`, `get pods --show-labels` |
