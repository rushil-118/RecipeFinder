# Design decisions



## Add an API instead of deploying the CLI
A command-line tool has nothing for Kubernetes to probe, route to or measure. The API reuses the same `Catalog`
code, so behaviour is identical, and gives health checks, metrics and a user journey to verify.
*Alternative:* run the CLI as a Kubernetes Job. Fine for batch work, but then there is nothing to keep running or observe.

## Deployment, 2 replicas, rolling update with `maxUnavailable: 0`
The service is stateless (the CSV is loaded into memory per pod), so any pod can answer. Two pods plus
`maxSurge: 1` / `maxUnavailable: 0` means an update starts a new pod and only removes an old one after the new one is
ready; a bad release never reduces capacity (the rollback demo shows this). A PodDisruptionBudget (`minAvailable: 1`)
protects against node drains.
*Alternative:* StatefulSet, only if each pod needed its own durable storage. HPA, if load varied (needs metrics-server; not worth it for a CSV lookup).

## Probes
- **Startup and readiness** use `/ready`: the catalog loaded at least one recipe. A pod that cannot answer correctly stays out of the Service.
- **Liveness** uses `/health`: only "can the process answer?". It is kept separate from readiness so a temporary
  data problem takes a pod out of traffic without restarting it in a loop.
- `FAIL_HEALTH` is a demo-only toggle to show liveness failure and recovery. It is off by default.

## Fail fast on bad data
If the CSV is malformed the app raises at startup, so the pod crash-loops visibly instead of serving wrong answers.

## Graceful shutdown
`preStop: sleep 5` keeps the pod serving while endpoint removal propagates, then SIGTERM makes gunicorn finish in-flight
requests (`--graceful-timeout 20`) inside the 30 s grace period.

## One gunicorn worker with threads
Metrics live in the process; several workers would each keep their own counters (Prometheus multiprocess mode would be
needed). Scale with pods, not workers.

## Helm and configuration
One chart; values hold everything that differs between environments, so there are no drifting copies of YAML.
`image.tag` has no default and the chart will not render without it, so an untraceable image cannot be deployed (CI checks this).
A config or flag change alters the ConfigMap checksum annotation, which rolls the pods.
*Alternative:* Kustomize (simpler patches, no templating). Helm wins here for release history, `rollback` and `--atomic`.

## Feature flag
`features.nutrition` switches the calories endpoint off (403) with a values change and a rollout, with no new image. It
separates "deployed" from "released" and gives a quick mitigation if that endpoint misbehaves.

## Keeping CI/CD simple
- **Two small workflows:** `ci.yml` checks the code and `cd.yml` deploys it. `ci.yml` calls `cd.yml` only after the checks pass (`needs: check`), so a broken change never reaches the deploy step. `cd.yml` is also runnable by hand, which is the manual-trigger option for deliberate deploys.
- **Why a workflow call and not a `workflow_run` trigger:** `workflow_run` only fires for workflow files on the default branch, so it would not run on a pull-request branch until merged.
- **One script does the delivery:** `scripts/deploy.sh` builds the image, loads it into the cluster, installs the chart and smoke-tests it. The pipeline and a developer's laptop run the same script, so there is no pipeline-only logic to debug.
- **No registry and no artifact hand-off:** the CD job builds the image and deploys it on the same runner, so the image that is deployed is the image that was just built. The tag is the git commit, so the running version is always traceable.
- **Ephemeral kind cluster:** proves the deploy path works end to end without paid infrastructure.
- **`--atomic`:** a release that does not become ready is rolled back by Helm automatically.
- **Deploy runs on every push:** acceptable because the target is throwaway. With a real cluster, add a GitHub Environment with required reviewers.
- **Cost of this simplicity:** CI does not produce an image, and CD builds it, so you cannot redeploy an already-built image or promote the same image to another environment.


## Security
- **Image:** multi-stage, no build tools, numeric non-root user.
- **Pod:** `runAsNonRoot`, read-only root filesystem (only `/tmp` writable), all capabilities dropped, no privilege escalation, seccomp `RuntimeDefault`, no service-account token.
- **Exposure:** ClusterIP only. A NetworkPolicy template exists but is off by default because a bare kind cluster may not enforce it.
- **Secrets:** the app needs none. `scripts/check-secrets.sh` rejects committed credentials in CI.
- **Pipeline:** workflow token is read-only (`permissions: contents: read`).
- **Input handling:** parameters are validated and bounded; unknown routes and methods return JSON errors.

## What would change under different requirements
| Requirement or failure | Change |
|---|---|
| Much more traffic | HPA (+ metrics-server), raise limits, consider caching at an ingress |
| Catalog changes often | Load from a ConfigMap, object store or database instead of baking the CSV in |
| Public exposure | Ingress + TLS, rate limiting, authentication |
| Several environments | Per-environment values files, GitHub Environments with approvals, Argo CD |
| A bad release is expensive | Canary with a metric gate, or blue-green |
| Pod keeps restarting | `kubectl logs --previous`, `describe pod` (exit code 137 = OOM), compare memory with the 192Mi limit |