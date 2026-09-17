# Mini-Task 2 — Your app + Redis, on Compose and on Kubernetes

**Handed out:** Week 2, Session B · **Due:** Week 3, Session A (start of class) · **Worth:** 10% of the course grade · **Individual work**

## The task

Take the `worker` service from Mini-Task 1 and make it use **Redis**. Then run the pair the two ways you did in the lab: with Compose, and on a k3d cluster. Finally, write down one difference between the two that you saw yourself.

No new starter code. Start from your Mini-Task 1 files (fix what the feedback said) and copy the pattern from the Week 2 lab.

**The feature:** a request counter. Every `POST /stats` adds one to a counter in Redis, and `GET /` shows it as `"requests_served": 17`. That's about ten lines of Python with the `redis` package (see `app/main.py` in the Week 2 repo for how the demo-app connects). Redis host and port come from environment variables `REDIS_HOST` and `REDIS_PORT` — never hard-coded.

If you didn't finish Mini-Task 1, you may use the Week 2 demo-app instead. Then add one new Redis endpoint of your own (for example `GET /items/count`) and write `compose.yaml` and `k8s/` yourself — don't copy from `solution/`.

## Deliverables

A zip or a repo link with:

1. **The app** — `app/`, `requirements.txt`, `Dockerfile`, `.dockerignore`. Multi-stage, non-root, pinned base tag, as in Mini-Task 1.
2. **`compose.yaml`** — `app` built from your Dockerfile, `redis` from `redis:7-alpine`, with:
    - a `healthcheck` on redis and `depends_on` with `condition: service_healthy` on the app
    - a named volume on `/data`
    - `REDIS_HOST` set in `environment:`
3. **`k8s/`** — a Deployment and a Service for the app, a Deployment and a Service for Redis. `kubectl apply -f k8s/` must work on a fresh cluster.
4. **`README.md`** with:
    - the commands to run each version from scratch (Compose; and k3d, including `k3d image import`)
    - the output of `docker compose ps` showing redis `(healthy)`
    - the output of `curl localhost:8000/` before and after `docker compose down` + `up` — the counter must survive
    - the output of `kubectl get pods` (all `Running 1/1`) and `kubectl get endpoints` (no `<none>`)
    - **3–5 sentences: one difference you observed** between the Compose and the Kubernetes version

Don't include `.venv/`, `__pycache__/`, `.env` or image files.

## What "one difference you observed" means

Something that *happened* on your screen, with the command that showed it, and why. Not a sentence from the internet.

- ✘ "Kubernetes is more scalable than Compose."
- ✔ "After `docker compose down` and `up` my counter was still 17. After `kubectl delete pod` on the redis Pod it was 0 — my Redis Deployment has no volume, so the data lived inside the Pod."
- ✔ "In Compose the app waited for Redis to be healthy. In Kubernetes both started at once and `curl` gave 503 for a few seconds until Redis was up — there is no `depends_on`."

The lab's Steps 7–9 and the debrief questions are full of these.

## How it's graded (10 pts)

| Criterion | Pts | Full marks |
|---|---|---|
| Compose stack healthy | 3 | `docker compose up -d --build` → `ps` shows app `Up`, redis `Up (healthy)`; the counter works; healthcheck and `depends_on` condition present |
| Volume persistence | 1 | Counter survives `down` + `up` |
| K8s manifests apply, Pods Ready | 3 | `kubectl apply -f k8s/` on a fresh k3d cluster → no errors, all Pods `Running 1/1`, counter works through `port-forward` |
| Service has endpoints | 1 | `kubectl get endpoints` shows an address for both Services; the app reaches Redis by the Service name |
| Observation | 2 | Real, specific, correctly explained |

Partial credit per criterion. Late = 0 unless you e-mailed before the deadline.

## Hints

- `depends_on: [redis]` without a `condition` only orders start-up; the app will still get `Connection refused`. Lab Step 2.2 has the right form.
- `localhost` inside a container is that container. Redis is called `redis` — the Compose service name, or the Kubernetes Service name.
- Before submitting, test on a fresh cluster: `k3d cluster delete cos`, `k3d cluster create cos`, import, apply. Leftovers from the lab hide mistakes.
- `ImagePullBackOff` → you forgot `k3d image import` or the tag doesn't match. `CrashLoopBackOff` → `kubectl logs <pod>`. `ENDPOINTS <none>` → selector vs. labels (lab Drill C).

## Academic honesty

Discussing with classmates is fine. Submitting files you didn't write, or an observation you didn't make, is not. If you used an AI assistant, say so in the README and be ready to explain every line.
