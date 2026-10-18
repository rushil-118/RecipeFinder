# Recipe Finder

A small command-line program that answers questions about a CSV of recipes: how many a cuisine has,
which ones, what is ready quickly, and the average calories.

The original program is still the command-line tool (`python -m recipefinder`). The same query code now also runs
as a small HTTP API, so it can stay up on Kubernetes, expose health and metrics, and log every request.

## Identity and baseline

| | |
|---|---|
| Name | Rushil D Choudhary |
| Student ID | 23BCS10178 |
| Project | Recipe Finder |
| Repository | https://github.com/rushil-118/RecipeFinder |
| **Baseline commit** | 9290355fb4f78669a00bbc9d9fb5c3566d26f1a8 |


## What this adds
 
| Area | Choice |
|---|---|
| Runtime | HTTP API (Flask + gunicorn) in a container, Kubernetes Deployment with 2 pods |
| Configuration | One Helm chart; values for image tag, feature flag, resources |
| Delivery | `ci.yml` checks the code; `cd.yml` builds the image, deploys it to a kind cluster and smoke-tests it |
| Release | Image tag is the git commit. Rolling update with `maxUnavailable: 0`. `helm rollback` restores the previous revision. Feature flag for the calories endpoint |
| Signals | JSON logs with request ID, Prometheus metrics, `/health` and `/ready`, alert rules with response actions |
| Security | Non-root read-only container, no Kubernetes API token, ClusterIP only, secret scan in CI, no secrets needed |
 
More detail: [docs/DECISIONS.md](docs/DECISIONS.md) (why) and [docs/OPERATIONS.md](docs/OPERATIONS.md) (signals, SLOs, failure demos).
 
## Request path and delivery path
 
```
 client ─► Service (ClusterIP :80) ─► one of 2 pods (:8080, gunicorn + Flask)
                                         └─ Catalog (CSV loaded into memory at startup)
 /health  = the process can answer          /ready = the catalog loaded at least one recipe
 /version = {version, commit}               /metrics = Prometheus
 
 git push ─► check (secret scan, lint, tests, helm lint)
          ─► build image recipe-finder:<commit> ─► kind cluster ─► helm upgrade --atomic ─► smoke test
          ─► bad-release demo
```
 
## Prerequisites
 
Python 3.12 for the CLI and tests. For Kubernetes: Docker, [kind](https://kind.sigs.k8s.io/), kubectl, Helm 3.
 
## Run it
 
**Command line**
```bash
pip install -r requirements-dev.txt
python -m recipefinder cuisines
python -m recipefinder count Italian
python -m recipefinder quick 20 --vegetarian
pytest
```
 
**API without Kubernetes**
```bash
gunicorn --bind 127.0.0.1:8080 "recipefinder.api:create_app()"
curl 'localhost:8080/recipes/count?cuisine=Italian'
```
 
**On local Kubernetes**
```bash
bash scripts/deploy.sh                 # build, create kind cluster, load image, helm install, smoke test
                                       # port 8080 busy? use: LOCAL_PORT=9000 bash scripts/deploy.sh
kubectl -n recipe-finder port-forward svc/recipe-finder 8080:80
curl localhost:8080/version
curl 'localhost:8080/recipes/names?cuisine=Thai'
curl localhost:8080/metrics
```
 
| Endpoint | Meaning |
|---|---|
| `GET /recipes/cuisines` | all cuisines |
| `GET /recipes/count?cuisine=Italian` | number of recipes |
| `GET /recipes/names?cuisine=Thai` | recipe names |
| `GET /recipes/quick?max_minutes=20&vegetarian=true` | ready within the time limit |
| `GET /recipes/calories?cuisine=Indian` | average calories (feature-flagged; `403` when off) |
 
## Failure demos
 
Bad release, then rollback (the app keeps serving because the rolling update never removes the last ready pods):
```bash
bash scripts/demo-rollback.sh
```
Pod replacement: `kubectl -n recipe-finder delete pod -l app.kubernetes.io/name=recipe-finder` then `bash scripts/smoke.sh http://localhost:8080`.
Liveness failure and recovery:
```bash
helm -n recipe-finder upgrade recipe-finder charts/recipe-finder --reuse-values --set failHealth=true     # pods restart
helm -n recipe-finder upgrade recipe-finder charts/recipe-finder --reuse-values --set failHealth=false    # the fix
```
Switch a feature off without a new image:
```bash
helm -n recipe-finder upgrade recipe-finder charts/recipe-finder --reuse-values --set features.nutrition=false
```
 
## Pipeline
 
Two workflow files. `ci.yml` runs on every push and pull request and, if it passes, calls `cd.yml`. `cd.yml` can also be started by hand from the Actions tab.
 
| File | What it does |
|---|---|
| `.github/workflows/ci.yml` | `check-secrets.sh`, ruff, pytest with an 85% coverage gate, `helm lint`. Nothing is deployed unless all of these pass |
| `.github/workflows/cd.yml` | `scripts/deploy.sh` builds `recipe-finder:<12-char commit>`, loads it into a kind cluster, runs `helm upgrade --atomic` and smoke-tests the running app; then `scripts/demo-rollback.sh` |
 
The same `deploy.sh` is what you run locally. The job summary records the commit, the pod images and the smoke-test result.
 
## Limitations
 
- The cluster is a throwaway kind cluster in the pipeline. There is no registry, no cloud account and no long-lived environment.
- The deploy job runs automatically on every push. A real production environment would add a manual approval step.
- The catalog is loaded once at startup; changing the CSV needs a new image.