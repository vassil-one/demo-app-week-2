# demo-app — Week 2

Student repo for **COS 3122A Cloud-Native Deployment, Week 2 (Docker Compose; Kubernetes fundamentals)**.

**Start here → [lab.md](lab.md).**

```bash
cd ~
git clone https://github.com/vassil-one/demo-app-week-2.git
cd demo-app-week-2
```

Same FastAPI app as Week 1, grown by one backing service (Redis). You'll write `compose.yaml` and `k8s/` yourself during the lab. The finished versions are in `solution/` — the lab tells you when to look.

## What's here

| File | Purpose |
|---|---|
| `lab.md` | **The Week 2 lab.** Numbered steps, expected output, debug drills |
| `app/main.py` | The application |
| `requirements.txt` | Pinned dependencies (FastAPI, uvicorn, redis) |
| `Dockerfile` | Multi-stage, non-root — the Week 1 reference solution |
| `.dockerignore` | Keeps junk (and secrets) out of the build context |
| `solution/compose.yaml` | Reference for lab Steps 2–3: app + Redis, healthcheck, `depends_on`, named volume |
| `solution/.env.example` | Variables Compose fills into `compose.yaml` |
| `solution/k8s/` | Reference for lab Steps 6–7: `deployment.yaml`, `service.yaml`, `redis.yaml` |

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /` | `{"message": "...", "version": "<APP_VERSION>", "hostname": "<container id / pod name>"}` |
| `GET /health` | `{"status": "ok"}` — never checks Redis |
| `GET /version` | `{"version": "<APP_VERSION>"}` |
| `GET /hostname` | `{"hostname": "..."}` — call it repeatedly to watch load-balancing |
| `GET /items` | `{"items": [...]}` — read from Redis |
| `POST /items` | body `{"name": "milk"}` → `{"added": "milk"}` |
| `DELETE /items` | wipes the list |

If Redis is unreachable, `/items` returns **503** with the host and port the app tried.

Configuration via environment variables:

| Variable | Default | Notes |
|---|---|---|
| `APP_VERSION` | `dev` (`v1` in the image) | shown in `/` and `/version` |
| `REDIS_HOST` | `localhost` | in Compose / Kubernetes this is the **service name** `redis` |
| `REDIS_PORT` | `6379` | must be a number — anything else crashes the app on start |

## Quick reference (after the lab)

```bash
# Compose
docker compose up -d --build
docker compose ps
curl localhost:8000/items
docker compose down          # keeps the volume
docker compose down -v       # deletes the volume too

# Kubernetes on k3d
k3d cluster create cos --port 8081:80@loadbalancer
docker build -t demo:v1 .
k3d image import demo:v1 -c cos
kubectl apply -f k8s/
kubectl get pods
kubectl get endpoints
kubectl port-forward service/demo 8000:80
```
