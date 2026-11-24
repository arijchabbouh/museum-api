# 🏛️ Museum Visits API

A small, gamified REST API: artists create virtual museums, visitors explore them,
and artists earn points and badges based on how many **different** people visit.

The API is intentionally small (< 150 lines). The real goal of this project is the
**DevOps pipeline around it**: CI/CD, Docker, Kubernetes, observability and security.

![CI](https://github.com/arijchabbouh/museum-api/actions/workflows/ci.yml/badge.svg)

## Architecture

```
 git push ──► GitHub Actions
                ├─ test     pytest + coverage, size check (< 150 lines)
                ├─ sast     Bandit
                ├─ build    Docker build + Trivy image scan
                ├─ push     Docker Hub (main only)
                └─ deploy-dast  kind cluster → kubectl apply → smoke test → OWASP ZAP

 Running API
   ├─ JSON logs (with trace_id)  → docker logs / kubectl logs
   ├─ /metrics                   → Prometheus → Grafana
   └─ traces (OpenTelemetry)     → Jaeger
```

## Tech stack

| Area | Tools |
|---|---|
| API | Python 3.12, Flask, Gunicorn |
| Tests | pytest, pytest-cov |
| Logs | python-json-logger (structured JSON) |
| Metrics | prometheus-client, Prometheus, Grafana |
| Tracing | OpenTelemetry, Jaeger |
| Containers | Docker (multi-stage, non-root), Docker Compose |
| Orchestration | Kubernetes (kind) |
| CI/CD | GitHub Actions |
| Security | Bandit (SAST), Trivy (image scan), OWASP ZAP (DAST) |

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check (used by Kubernetes probes) |
| GET | `/metrics` | Prometheus metrics |
| GET | `/museums` | List all museums |
| POST | `/museums` | Create a museum `{"name", "theme", "artist"}` |
| GET | `/museums/<id>` | Get one museum |
| GET | `/artists/<artist>/museums` | Museums of one artist |
| POST | `/visits` | Log a visit `{"visitor", "museum_id"}` |
| GET | `/artists/<artist>` | Artist profile: visits, points, badge |
| GET | `/leaderboard` | Top 10 artists by points |

### Business rules
- A visit gives the artist **10 points**, but only the **first** visit of a visitor to a museum counts
- An artist visiting their **own** museum gets no points
- Badges depend on unique visitors: 🥉 bronze ≥ 3, 🥈 silver ≥ 5, 🥇 gold ≥ 10

Data is stored in memory (reset on restart), to keep the service small.

### Examples (PowerShell)
```powershell
# Create a museum
$m = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/museums -ContentType "application/json" `
      -Body '{"name":"Pixel Dreams","theme":"retro games","artist":"arij"}').id

# Log a visit
Invoke-RestMethod -Method Post -Uri http://localhost:8000/visits -ContentType "application/json" `
  -Body "{`"visitor`":`"nour`",`"museum_id`":`"$m`"}"

# Artist profile and leaderboard
Invoke-RestMethod http://localhost:8000/artists/arij
Invoke-RestMethod http://localhost:8000/leaderboard
```

### Examples (curl)
```bash
curl -X POST http://localhost:8000/museums -H "Content-Type: application/json" \
     -d '{"name":"Pixel Dreams","theme":"retro games","artist":"arij"}'
curl -X POST http://localhost:8000/visits -H "Content-Type: application/json" \
     -d '{"visitor":"nour","museum_id":"<museum-id>"}'
curl http://localhost:8000/artists/arij
curl http://localhost:8000/leaderboard
```

## Run locally (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -v --cov=app      # run the tests
flask --app app.main run --port 8000
```

## Docker

```bash
docker build -t museum-api .
docker run -d --name museum -p 8000:8080 museum-api
docker logs museum
```
The image is published on Docker Hub: [`arijengineer/museum-api`](https://hub.docker.com/r/arijengineer/museum-api)

### Full stack with monitoring (Docker Compose)
```bash
docker compose up -d --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Grafana dashboard | http://localhost:3000/d/museum-api |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |

The Grafana data source and dashboard are provisioned from files in `monitoring/` (no manual setup).

## Kubernetes (kind)

```bash
kind create cluster --name museum
kubectl apply -f k8s/
kubectl get pods
kubectl port-forward svc/museum-api 8000:80
kubectl logs deployment/museum-api
```
Manifests: `ConfigMap` (configuration), `Deployment` (1 replica, readiness/liveness
probes on `/health`, resource limits, non-root), `Service` (NodePort).

## CI/CD

The pipeline (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | What it does |
|---|---|
| `test` | pytest with coverage, checks `app/main.py` < 150 lines |
| `sast` | Bandit static analysis, report saved as artifact |
| `build` | Builds the image and scans it with Trivy (CRITICAL/HIGH) |
| `push` | On `main` only: pushes the image to Docker Hub (tags: commit SHA + `latest`) |
| `deploy-dast` | Deploys to a kind cluster, smoke test, OWASP ZAP baseline scan |

Required repository secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

## Observability

- **Logs**: one JSON line per request (method, path, status, duration, `trace_id`); errors logged with stack traces
- **Metrics**: `http_requests_total`, `http_request_duration_seconds`, `museum_visits_total`
- **Tracing**: automatic Flask spans + custom spans (`store_visit`, `compute_leaderboard`), viewable in Jaeger.
  The `trace_id` in the logs links a log line to its trace.

## Security

| Check | Tool | Result |
|---|---|---|
| SAST | Bandit | No medium/high issues |
| Image scan | Trivy | 0 CRITICAL/HIGH vulnerabilities |
| DAST | OWASP ZAP | 0 High / Medium / Low after adding security headers |

Other measures: non-root container, Kubernetes security context, secrets stored in GitHub Secrets.

## Project structure

```
app/main.py              the API (< 150 lines)
tests/test_app.py        unit tests
Dockerfile               multi-stage, non-root image
docker-compose.yml       API + Prometheus + Grafana + Jaeger
monitoring/              Prometheus config, Grafana provisioning and dashboard
k8s/                     Kubernetes manifests
.github/workflows/ci.yml CI/CD pipeline
```

## Limitations and future improvements
- Data is in memory → a database (e.g. PostgreSQL) would allow persistence and several replicas
- No authentication → anyone can use any artist name (JWT authentication would fix it)
- Prometheus data is lost on restart → add a persistent volume