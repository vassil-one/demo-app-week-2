# Week 2 — Lab (Session B)

**Goal:** everything from Session A, by your own hands: wire the demo-app to Redis with Compose and prove where the data lives; then create a Kubernetes cluster on your laptop, put the same two services on it with your first manifests, watch it heal and load-balance, and diagnose the three failures you'll see most often this semester.

**Rules of the lab**

- Type the commands. Don't paste.
- Every step ends with a **Check:** line. Don't move on until you see it.
- Stuck for more than 10 minutes? Raise a hand.
- Keep **two terminals** open all lab: one for commands, one for `curl` and for watching.

Get the code. The repo has the app, this document, and a `solution/` folder — don't look in there until Step 10.

```bash
cd ~
git clone https://github.com/vassil-one/demo-app-week-2.git
cd demo-app-week-2
ls
```

```
app  Dockerfile  lab.md  README.md  requirements.txt  solution
```

Windows: everything in the **Ubuntu (WSL2)** terminal. All commands below are run from inside `demo-app-week-2`.

No k3d on your machine, or on a lab machine? You can do the whole lab in a free online environment instead — see the box **"No local Kubernetes? Use iximiuz Labs"** before Step 4.

---

## Step 1 — Build the Week 2 app (5 min)

The app grew since last week: `/items` (GET/POST, stored in Redis) and `/hostname`. The `Dockerfile` is the Week 1 reference solution (your own from last week works too).

```bash
cat requirements.txt
docker build -t demo:v1 .
```

```
fastapi==0.115.6
uvicorn==0.34.0
redis==5.2.1
```

Open `app/main.py`. Find `REDIS_HOST` and `REDIS_PORT`, and read what `require_redis()` does when Redis isn't there. Then run the image alone, as in Week 1:

```bash
docker run --rm -d --name solo -p 8000:8000 demo:v1
curl localhost:8000/
curl localhost:8000/items
docker stop solo
```

```
{"message":"Hello from demo-app v1","version":"v1","hostname":"57e11be6e842"}
{"detail":"redis unreachable at localhost:6379: Error 111 connecting to localhost:6379. Connection refused."}
```

`/` works, `/items` doesn't: the app needs a second container. Read the error carefully: it tells you *where* the app looked. You'll see this exact message twice more today, each time for a different reason.

**Check:** `demo:v1` built; `/items` returns 503 with `localhost:6379` in the message.

---

## Step 2 — Two containers by hand, then Compose (12 min)

### 2.1 The manual way, once

```bash
docker network create demo-net
docker run -d --name redis --network demo-net redis:7-alpine
docker run -d --name app --network demo-net -p 8000:8000 -e REDIS_HOST=redis demo:v1
curl -X POST localhost:8000/items -H 'content-type: application/json' -d '{"name":"milk"}'
curl localhost:8000/items
```

```
{"added":"milk"}
{"items":["milk"]}
```

`-e REDIS_HOST=redis` — the app reached Redis by the *container name*, resolved by the network's built-in DNS. See it from a third container:

```bash
docker run --rm --network demo-net alpine getent hosts redis
```

```
172.19.0.2        redis  redis
```

Four commands and a handful of flags, for two services. Tear it down; Compose will do all of this for you.

```bash
docker rm -f app redis
docker network rm demo-net
```

### 2.2 Write `compose.yaml`

Create a file called `compose.yaml` in the repo folder. Two services: the app is *built* from your Dockerfile; Redis is *pulled*. Type it in this order and think about each line:

```yaml
services:
  app:
    build: .
    image: demo:v1
    ports:
      - "8000:8000"
    environment:
      REDIS_HOST: redis
      REDIS_PORT: "6379"
    depends_on:
      redis:
        condition: service_healthy

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

- `REDIS_HOST: redis` — the **service name** is the hostname, exactly like the container name in 2.1. No IPs, ever.
- `healthcheck` runs `redis-cli ping` *inside* the redis container every 5 s; `depends_on … service_healthy` makes `app` wait for it to pass.
- `redis-data:/data` — a **named volume** (declared at the bottom) mounted where Redis writes its snapshots.

⚠️ YAML: indent with **two spaces**, never tabs. If `docker compose up` says `yaml: line N`, the problem is on or just above that line.

```bash
docker compose up -d --build
docker compose ps
```

```
[+] Running 4/4
 ✔ Network demo-app-week-2_default      Created
 ✔ Volume demo-app-week-2_redis-data    Created
 ✔ Container demo-app-week-2-redis-1    Healthy
 ✔ Container demo-app-week-2-app-1      Started
NAME                       IMAGE            COMMAND                  SERVICE   STATUS                    PORTS
demo-app-week-2-app-1      demo:v1          "uvicorn app.main:ap…"   app       Up 2 seconds              0.0.0.0:8000->8000/tcp
demo-app-week-2-redis-1    redis:7-alpine   "docker-entrypoint.s…"   redis     Up 8 seconds (healthy)    6379/tcp
```

Notice the order: Redis *Healthy* **before** the app *Started*. Everything is prefixed with the project name, which is the folder name.

### 2.3 Prove where the data lives

```bash
curl -X POST localhost:8000/items -H 'content-type: application/json' -d '{"name":"milk"}'
curl -X POST localhost:8000/items -H 'content-type: application/json' -d '{"name":"eggs"}'
curl localhost:8000/items
docker compose down
docker compose up -d
curl localhost:8000/items
```

```
{"added":"milk"}
{"added":"eggs"}
{"items":["milk","eggs"]}
[+] Running 3/3
 ✔ Container demo-app-week-2-app-1    Removed
 ✔ Container demo-app-week-2-redis-1  Removed
 ✔ Network demo-app-week-2_default    Removed
…
{"items":["milk","eggs"]}
```

Both containers were **removed** and recreated, and the list survived. Look at what `down` did *not* remove:

```bash
docker volume ls
docker volume inspect demo-app-week-2_redis-data
```

```
DRIVER    VOLUME NAME
local     demo-app-week-2_redis-data
[{ "Mountpoint": "/var/lib/docker/volumes/demo-app-week-2_redis-data/_data", … }]
```

That folder on your disk is where `milk` and `eggs` are (Redis' `dump.rdb`). Now delete it on purpose:

```bash
docker compose down -v
docker compose up -d
curl localhost:8000/items
```

```
 ✔ Volume demo-app-week-2_redis-data  Removed
…
{"items":[]}
```

Why does the list survive `down` but not `down -v`? Write your one-sentence answer down; it's debrief question 1.

### 2.4 The dev loop

```bash
docker compose logs app
docker compose exec app hostname
docker compose exec app env
docker compose exec redis redis-cli lrange items 0 -1
```

The last one reads the list straight out of Redis, no app involved. Add an item through the app and run it again.

**Check:** items survive `down` + `up`, are gone after `down -v`, and you can read them with `redis-cli` inside the redis container.

---

## Step 3 — Config from a `.env` file (5 min)

Hard-coding `8000` and `redis` in `compose.yaml` is fine until you have two environments. Compose fills in `${VAR}` from a file named `.env` next to it. Change two lines in `compose.yaml`:

```yaml
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      REDIS_HOST: ${REDIS_HOST:-redis}
```

`${APP_PORT:-8000}` means "the value of `APP_PORT`, or `8000` if it isn't set". Now create a file called `.env` with exactly these two lines:

```
APP_PORT=8002
REDIS_HOST=redis
```

```bash
docker compose config
docker compose up -d
curl localhost:8002/items
```

In the `config` output, find `published: "8002"` under `ports` and `REDIS_HOST: redis` under `environment`. `docker compose config` prints the file *with the variables filled in* — your first stop whenever `.env` surprises you.

```
{"items":[]}
```

Only the app container was recreated (its config changed; Redis' didn't). Now the pitfall from the slides, on purpose. Edit `.env` and change `redis` to `localhost`:

```
APP_PORT=8002
REDIS_HOST=localhost
```

```bash
docker compose up -d
curl localhost:8002/items
```

```
{"detail":"redis unreachable at localhost:6379: Error 111 connecting to localhost:6379. Connection refused."}
```

Same message as Step 1, different reason: `localhost` inside the `app` container is the app container's **own** loopback. Redis is a different container = a different net namespace = a different `localhost`. Change it back to `redis`, run `docker compose up -d` again, and leave the stack running.

🔒 `.env` is where real passwords end up. It's already in this repo's `.gitignore`; do the same in your own projects, and commit a `.env.example` instead.

**Check:** the app answers on port 8002 without touching `compose.yaml`; you can explain why `localhost` failed.

---

## Step 4 — A Kubernetes cluster on your laptop (5 min)

> ### No local Kubernetes? Use iximiuz Labs
>
> **https://labs.iximiuz.com/playgrounds → K3s.** Free account (sign in with GitHub or Google). You get a browser terminal on a machine called `dev-machine` that has Docker, `kubectl`, and a running three-node cluster. Sessions have a time limit; if yours expires, start a new one and clone again.
>
> Do the lab **in that terminal**, with these differences:
>
> 1. **Clone there.** Same commands as at the top of this document: `cd ~`, `git clone …`, `cd demo-app-week-2`. Write `compose.yaml` and the `k8s/` files with `nano`.
> 2. **Steps 1–3 (Docker, Compose): as written.**
> 3. **Step 4: skip `k3d cluster create`.** The cluster already exists. `kubectl get nodes` shows `cplane-01`, `node-01`, `node-02` instead of `k3d-cos-server-0`.
> 4. **Step 5: push instead of import.** The cluster nodes can't see the image on `dev-machine`, but the playground has its own registry they can pull from. Instead of `k3d image import`, run:
>    ```bash
>    docker tag demo:v1 registry.iximiuz.com/demo:v1
>    docker push registry.iximiuz.com/demo:v1
>    ```
> 5. **Step 6: use the registry name.** In `k8s/deployment.yaml` write `image: registry.iximiuz.com/demo:v1` instead of `image: demo:v1`.
> 6. **Everything else is identical.** Step 10: just close the tab instead of `k3d cluster stop`. In Dig deeper, skip D3 and D7 (they look inside the k3d node container).
>
> Other online clusters are listed in the appendix at the end; use them only if iximiuz Labs is down.

```bash
k3d cluster create cos --port 8081:80@loadbalancer
```

```
INFO[0000] Prep: Network
INFO[0000] Created image volume k3d-cos-images
INFO[0001] Creating node 'k3d-cos-server-0'
INFO[0003] Creating LoadBalancer 'k3d-cos-serverlb'
…
INFO[0025] Cluster 'cos' created successfully!
```

`--port 8081:80@loadbalancer` maps your laptop's 8081 to the cluster's port 80; we won't use it until Ingress next week, but creating the cluster right is cheaper than recreating it. Look around:

```bash
kubectl cluster-info
kubectl get nodes
kubectl get all -A
```

```
Kubernetes control plane is running at https://0.0.0.0:41233
CoreDNS is running at https://0.0.0.0:41233/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

NAME               STATUS   ROLES           AGE   VERSION
k3d-cos-server-0   Ready    control-plane   20s   v1.3x.y+k3s1

NAMESPACE     NAME                                          READY   STATUS      RESTARTS   AGE
kube-system   pod/coredns-…                                 1/1     Running     0          30s
kube-system   pod/local-path-provisioner-…                  1/1     Running     0          30s
kube-system   pod/metrics-server-…                          1/1     Running     0          30s
kube-system   pod/traefik-…                                 1/1     Running     0          20s
kube-system   pod/svclb-traefik-…                           2/2     Running     0          20s
…
```

Kubernetes runs *itself* as Pods: CoreDNS is the cluster DNS you'll use in Step 7; Traefik is the Ingress controller for Week 3. They live in the `kube-system` namespace; your work goes in `default`. (Right after creation some are still `ContainerCreating`; run it again after 30 s.)

💡 Where is this "node"? Run `docker ps` — it's a container. k3d = k3s (a small Kubernetes) inside Docker. Every "machine" in your cluster is a container on your laptop, which is why the cluster took 25 seconds.

**Check:** one node `Ready`; `kubectl get all -A` shows the system pods `Running`.

---

## Step 5 — Get the image into the cluster (3 min)

(iximiuz Labs? Run the first two commands below to see the failure, then `docker tag` + `docker push` from the box above instead of `k3d image import`. `crictl` runs on the node, so use `kubectl describe pod` to confirm the image was pulled.)

Deploy before importing, just once, to see what happens (this comes back as Drill A, so look closely):

```bash
kubectl create deployment demo --image=demo:v1
kubectl get pods
```

```
NAME                    READY   STATUS             RESTARTS   AGE
demo-5b7f9c6d4-qk2xw    0/1     ErrImagePull       0          8s
```

Run `kubectl get pods` again after a few seconds: `ImagePullBackOff`. The cluster's container runtime (containerd, inside the k3d node) has its own image store and never sees your Docker images. `demo:v1` doesn't exist on Docker Hub either, so the pull fails. Delete that, import, and check:

```bash
kubectl delete deployment demo
k3d image import demo:v1 -c cos
docker exec k3d-cos-server-0 crictl images
```

```
INFO[0004] Successfully imported image(s)
IMAGE                                   TAG       IMAGE ID        SIZE
docker.io/library/demo                  v1        c354b5f07746e   146MB
docker.io/rancher/mirrored-coredns-…    …
…
```

`crictl` is `docker images` for containerd: it shows what the *node* has. Real clusters pull from a registry (Week 4); on a laptop, import.

**Check:** `crictl images` inside the node lists `demo` with tag `v1`.

---

## Step 6 — Your first manifests: Deployment + Service (10 min)

```bash
mkdir k8s
```

### 6.1 `k8s/deployment.yaml`

Create the file with this content:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
  labels:
    app: demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      containers:
        - name: demo
          image: demo:v1
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          env:
            - name: APP_VERSION
              value: "v1"
            - name: REDIS_HOST
              value: "redis"
            - name: REDIS_PORT
              value: "6379"
```

Before applying, name the four top-level parts and find the two lines that must agree (`selector.matchLabels` and `template.metadata.labels`). `imagePullPolicy: IfNotPresent` says "use what's in the node's store if it's there".

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods
kubectl get deployments
kubectl get replicasets
```

```
deployment.apps/demo created
NAME                    READY   STATUS    RESTARTS   AGE
demo-6dc894f97b-dr9td   1/1     Running   0          6s

NAME   READY   UP-TO-DATE   AVAILABLE   AGE
demo   1/1     1            1           6s

NAME              DESIRED   CURRENT   READY   AGE
demo-6dc894f97b   1         1         1       6s
```

You wrote one object; you got three. The Pod name is `<deployment>-<replicaset hash>-<random>`: the Deployment owns the ReplicaSet, the ReplicaSet owns the Pod.

### 6.2 Inspect it the four ways

Your Pod has a random name. Copy it from `kubectl get pods` and use it wherever you see `<pod>` below.

```bash
kubectl describe pod <pod>
```

Scroll to the bottom, to **Events**:

```
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  40s   default-scheduler  Successfully assigned default/demo-6dc894f97b-dr9td to k3d-cos-server-0
  Normal  Pulled     40s   kubelet            Container image "demo:v1" already present on machine and can be accessed by the pod
  Normal  Created    40s   kubelet            Container created
  Normal  Started    40s   kubelet            Container started
```

Events is where every "why is my Pod not running" answer starts. `already present on machine` is your import from Step 5.

```bash
kubectl logs <pod>
kubectl exec <pod> -- hostname
kubectl exec <pod> -- env
```

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-… INFO demo-app v1 starting on demo-6dc894f97b-dr9td
2026-… INFO redis target: redis:6379
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

demo-6dc894f97b-dr9td

…
REDIS_PORT=6379
REDIS_HOST=redis
…
```

The hostname is now the Pod name (compare: container ID in Docker). The `env` output is long; find your three variables in it.

### 6.3 `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: demo
spec:
  type: ClusterIP
  selector:
    app: demo
  ports:
    - port: 80
      targetPort: 8000
```

```bash
kubectl apply -f k8s/service.yaml
kubectl get service demo
kubectl get endpoints demo
```

```
service/demo created
NAME   TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
demo   ClusterIP   10.43.47.231   <none>        80/TCP    3s
NAME   ENDPOINTS        AGE
demo   10.42.0.5:8000   3s
```

(Newer `kubectl` prints a warning that `endpoints` is deprecated. Ignore it today.) The endpoint IP is the Pod's IP — check with `kubectl get pods -o wide`. The Service found it through the selector; nobody typed that IP.

### 6.4 Reach it

A ClusterIP is reachable from *inside* the cluster only. Open a tunnel in the **second terminal** and leave it running:

```bash
kubectl port-forward service/demo 8000:80
```

Back in the first terminal:

```bash
curl localhost:8000/
curl localhost:8000/items
```

```
{"message":"Hello from demo-app v1","version":"v1","hostname":"demo-6dc894f97b-dr9td"}
{"detail":"redis unreachable at redis:6379: Error -2 connecting to redis:6379. Name or service not known."}
```

Third time you see this error, third reason: the name `redis` doesn't resolve *yet*, because nothing in the cluster is called `redis`.

**Check:** `/` answers through the port-forward with the Pod name as hostname; `/items` fails with `Name or service not known`.

---

## Step 7 — Redis as a Deployment + Service (5 min)

Kubernetes has no `depends_on` and no `healthcheck` in the Compose sense. Redis is just another Deployment, and its Service gives it the DNS name the app is already looking for. Two objects in one file, separated by a line with `---`.

Create `k8s/redis.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

```bash
kubectl apply -f k8s/redis.yaml
kubectl get pods
```

```
deployment.apps/redis created
service/redis created
NAME                     READY   STATUS    RESTARTS   AGE
demo-6dc894f97b-dr9td    1/1     Running   0          5m
redis-c46d5dffc-z9nj5    1/1     Running   0          9s
```

(If redis shows `ContainerCreating`, it's being pulled — run `kubectl get pods` again.) `redis:7-alpine` is a public image, so the node pulled it itself. The app was never restarted; try it again:

```bash
curl -X POST localhost:8000/items -H 'content-type: application/json' -d '{"name":"milk"}'
curl localhost:8000/items
kubectl exec <pod> -- getent hosts redis
kubectl get service redis
```

```
{"added":"milk"}
{"items":["milk"]}
10.43.24.110    redis.default.svc.cluster.local
NAME    TYPE        ClusterIP   10.43.24.110   <none>        6379/TCP   40s
```

(If the first request says `Timeout connecting to server`, Redis was `Running` but not listening yet; wait two seconds and repeat.) Inside the app Pod, `redis` resolves to the Service's ClusterIP, and kube-proxy forwards that to the Redis Pod. Same pattern as Compose, one level of indirection more.

Compare the two versions and write down one difference you *observed* (not one you read about) — that's what Mini-Task 2's README asks for. Hint: what happened in Compose when Redis wasn't ready yet, and what happens here? Where is the volume?

**Check:** `/items` works through the port-forward; `redis` resolves to the Service IP from inside the app Pod.

---

## Step 8 — Self-healing and scaling (5 min)

### 8.1 Kill a Pod

Stop the port-forward in the second terminal (Ctrl+C) and start a watch there instead. Leave it running:

```bash
kubectl get pods -w
```

First terminal:

```bash
kubectl delete pod <pod>
```

Watch the second terminal:

```
NAME                    READY   STATUS        RESTARTS   AGE
demo-6dc894f97b-dr9td   1/1     Running       0          8m
demo-6dc894f97b-dr9td   1/1     Terminating   0          8m
demo-6dc894f97b-wtkl2   0/1     Pending       0          0s
demo-6dc894f97b-wtkl2   0/1     ContainerCreating   0    0s
demo-6dc894f97b-wtkl2   1/1     Running       0          2s
```

Nobody restarted anything. The ReplicaSet saw 0 Pods where it wants 1 and made one. Note the new name: the old one is gone for good, which is the whole point — never depend on a Pod's name.

### 8.2 Scale

```bash
kubectl scale deployment demo --replicas=2
kubectl get pods
kubectl get endpoints demo
```

```
deployment.apps/demo scaled
NAME                    READY   STATUS    RESTARTS   AGE
demo-6dc894f97b-mqtkd   1/1     Running   0          4s
demo-6dc894f97b-wtkl2   1/1     Running   0          1m
redis-c46d5dffc-z9nj5   1/1     Running   0          6m
NAME   ENDPOINTS                       AGE
demo   10.42.0.5:8000,10.42.0.9:8000   6m
```

Two Pods, and the Service picked up the second endpoint by itself. To see it load-balance you need to be *inside* the cluster (port-forward sticks to one Pod). Start a throwaway Pod with a shell:

```bash
kubectl run box --rm -it --restart=Never --image=alpine:3.20 -- sh
```

You get a `/ #` prompt inside the cluster (ignore the notice about the session being recorded). Type this a few times:

```
wget -qO- http://demo/hostname
wget -qO- http://demo/hostname
wget -qO- http://demo/hostname
wget -qO- http://demo/hostname
```

```
{"hostname":"demo-6dc894f97b-mqtkd"}
{"hostname":"demo-6dc894f97b-wtkl2"}
{"hostname":"demo-6dc894f97b-wtkl2"}
{"hostname":"demo-6dc894f97b-mqtkd"}
```

`http://demo/` — port 80 of the Service, no port-forward, no IP. Two hostnames = two Pods behind one name. Now `wget -qO- http://demo/items` twice. Same answer both times — why? Type `exit` to leave (the Pod deletes itself).

⚠️ `kubectl scale` changed the *cluster*, not your file. Open `k8s/deployment.yaml` and change `replicas: 1` to `replicas: 2` so the file stays the truth. You'll need that in the next step.

**Check:** a deleted Pod is replaced within seconds; `/hostname` alternates between two Pod names; your file says `replicas: 2`.

---

## Step 9 — Debug drills (10 min)

The three failures you will hit most. Reproduce, read the symptom, fix. Keep `kubectl get pods -w` running in the second terminal throughout.

### Drill A — `ImagePullBackOff`: the image isn't where the cluster looks

```bash
kubectl set image deployment/demo demo=demo:v2
kubectl get pods
```

```
NAME                    READY   STATUS             RESTARTS   AGE
demo-6dc894f97b-mqtkd   1/1     Running            0          5m
demo-6dc894f97b-wtkl2   1/1     Running            0          6m
demo-7f9b4c5d8-x2h7q    0/1     ImagePullBackOff   0          20s
redis-c46d5dffc-z9nj5   1/1     Running            0          9m
```

Describe the broken one (copy its name) and read the Events at the bottom:

```bash
kubectl describe pod <broken pod>
```

```
  Normal   BackOff    18s               kubelet  Back-off pulling image "demo:v2"
  Warning  Failed     18s               kubelet  Error: ImagePullBackOff
  Warning  Failed     6s (x2 over 18s)  kubelet  Failed to pull image "demo:v2": … pull access denied, repository does not exist or may require authorization
```

Two things to notice. Events told you exactly why. And the two old Pods are still `Running`: the Deployment starts the new version *next to* the old one and won't remove the old until the new is ready (rolling update — Week 3). Causes in real life: forgot `k3d image import`, typo in the tag, private registry without credentials.

Fix by re-applying the file (declarative: the file says `v1`):

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods
```

The broken Pod disappears; the two `v1` Pods never moved.

### Drill B — `CrashLoopBackOff`: the container starts and dies

```bash
kubectl set env deployment/demo REDIS_PORT=abc
kubectl get pods
```

```
NAME                    READY   STATUS             RESTARTS      AGE
demo-84d5f6b7c9-n4k2p   0/1     CrashLoopBackOff   2 (15s ago)   40s
demo-84d5f6b7c9-t8w3z   0/1     Error              2 (12s ago)   40s
redis-c46d5dffc-z9nj5   1/1     Running            0             10m
```

The image pulled fine; the process exits right after starting. kubelet restarts it, it dies again (`Error`), and the wait between restarts grows (10 s, 20 s, 40 s … up to 5 min) — `CrashLoopBackOff` is that waiting state. The old, working Pods are **gone** this time. Why did the Deployment keep them in Drill A but replace them here? Because the new container *started*: without a readiness probe, "Running" counts as "Ready", so the Deployment saw a successful rollout and removed the old Pods a moment before the new ones crashed. In Drill A the container never started at all. Week 3 fixes this with probes.

Where's the reason for the crash? Same place as in Docker:

```bash
kubectl logs <crashing pod>
```

```
  File "/app/app/main.py", line 21, in <module>
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: invalid literal for int() with base 10: 'abc'
```

If you get nothing because the container just restarted, `kubectl logs <pod> --previous` shows the output of the *last* dead container. Fix, again, from the file:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods
```

### Drill C — `<none>` endpoints: the Service points at nothing

Change one word. In `k8s/service.yaml`, change the selector from `app: demo` to `app: demo-app`. Then:

```bash
kubectl apply -f k8s/service.yaml
kubectl get pods
kubectl get service demo
kubectl get endpoints demo
```

```
NAME                    READY   STATUS    RESTARTS   AGE
demo-6dc894f97b-…       1/1     Running   0          2m
demo-6dc894f97b-…       1/1     Running   0          2m
NAME   TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
demo   ClusterIP   10.43.47.231   <none>        80/TCP    20m
NAME   ENDPOINTS   AGE
demo   <none>      20m
```

Everything looks fine — Pods `Running`, Service present — and nothing works. Try from inside the cluster:

```bash
kubectl run box --rm -it --restart=Never --image=alpine:3.20 -- sh
```

```
wget -qO- http://demo/hostname
```

```
wget: can't connect to remote host (10.43.47.231): Connection refused
```

Type `exit`. Nothing red anywhere in `kubectl get`, the name resolves, and the connection is refused by a Service with nobody behind it. This is the one that costs people an afternoon. The move: `kubectl get endpoints` first; `<none>` → compare the Service's selector with the Pods' labels:

```bash
kubectl describe service demo
kubectl get pods --show-labels
```

```
Name:              demo
Selector:          app=demo-app
…
NAME                    READY   STATUS    …   LABELS
demo-6dc894f97b-mqtkd   1/1     Running   …   app=demo,pod-template-hash=6dc894f97b
```

`app=demo-app` ≠ `app=demo`. Fix the selector back to `app: demo`, apply, and `kubectl get endpoints demo` fills in again without restarting anything.

**Check:** for each drill you can say the symptom, the one command that revealed the cause, and the fix — in one sentence each.

---

## Step 10 — Clean up and debrief (5 min)

Stop the watch in the second terminal (Ctrl+C). Keep the cluster if your laptop has the RAM (it's needed again next week and costs ~1 GB idle); otherwise stop it:

```bash
k3d cluster stop cos
docker compose down
docker ps -a
docker volume ls
```

(`k3d cluster delete cos` removes it completely; `k3d cluster start cos` brings a stopped one back.)

⚠️ Leaving old clusters *running* is the top cause of "Docker is slow" — `k3d cluster list` before you blame your laptop.

Now open `solution/` and compare with what you wrote:

```bash
diff compose.yaml solution/compose.yaml
diff k8s/deployment.yaml solution/k8s/deployment.yaml
diff k8s/service.yaml solution/k8s/service.yaml
diff k8s/redis.yaml solution/k8s/redis.yaml
```

The reference has comments and a couple of `${…}` defaults; the objects are the same. Other differences are fine if you can explain them.

Debrief questions (together):

1. Why did the items survive `docker compose down` but not `down -v`? Where exactly were they?
2. The same 503 appeared three times today (Step 1, Step 3, Step 6). What was different each time?
3. In Drill A the old Pods kept running; in Drill B they were replaced. Why?
4. Drill C: nothing was red, yet the connection was refused. Which command would you run *first* next time and why?
5. Kubernetes has no `depends_on`. What did the app do instead while Redis wasn't there, and is that good enough for a real app?

**Mini-Task 2** is handed out now: [mini-task.md](mini-task.md). Due Week 3, Session A.

---

## Dig deeper (when you're done — pick what interests you)

Each one stands alone. **Tier 1 for everyone with time; Tier 2 and 3 by choice.** Start the Compose stack again (`docker compose up -d`) for D1 and D2.

### Tier 1 — make it physical

#### D1. Find the bridge and the cables

```bash
docker network inspect demo-app-week-2_default
ip link
```

In the first output, find the two containers and their `IPv4Address`. In the second, find a `br-…` line (the bridge = a virtual switch that `docker compose up` created) and the `veth…` lines (one virtual cable per container, `master br-…`). Compare with Week 1: same trick, now automated. (macOS: run `ip link` inside `docker run --rm -it --net=host --privileged alpine sh`.)

**Check:** you found the bridge and two veth lines that belong to it.

#### D2. The volume is just a folder

```bash
docker compose exec redis redis-cli save
sudo ls -la /var/lib/docker/volumes/demo-app-week-2_redis-data/_data
sudo strings /var/lib/docker/volumes/demo-app-week-2_redis-data/_data/dump.rdb
```

Your items, in a file, on your disk, outside any container. That's all a named volume is: a folder whose lifecycle Docker manages separately from containers. (macOS: from inside `docker run --rm -it --privileged --pid=host alpine`, the path is the same inside the VM.)

**Check:** you found your item names inside `dump.rdb`.

#### D3. The node is a container, the runtime is containerd

```bash
docker ps
docker exec k3d-cos-server-0 crictl ps
docker exec k3d-cos-server-0 crictl images
```

`crictl ps` shows *your* demo and redis containers as containerd sees them — no Docker daemon anywhere in that node. Match the names with `kubectl get pods -A`.

**Check:** you can point at the demo container in `crictl ps`.

### Tier 2 — the API underneath kubectl

#### D4. What the cluster actually stored

```bash
kubectl get deployment demo -o yaml
kubectl get pod <pod> -o yaml
```

Your 25-line file came back as ~150 lines: defaults were filled in (`strategy`, `progressDeadlineSeconds`, …) and a `status:` block was added that you never wrote. In the Pod's YAML, near the top, find `ownerReferences`: it points at the ReplicaSet, whose own YAML points at the Deployment. Now delete the ReplicaSet (`kubectl get replicasets`, then `kubectl delete replicaset <name>`) and watch the Deployment make a new one *and* new Pods. Then `kubectl explain deployment.spec.strategy` — built-in docs for every field.

**Check:** you found the `status` block and the `ownerReferences`.

#### D5. kubectl is just HTTP

```bash
kubectl get pods -v=8
```

Among the debug output, find the `"Request"` line with the URL (`…/api/v1/namespaces/default/pods`) and the `"Response"` line with `200 OK`. Every kubectl verb is a REST call to the API server. Talk to it yourself: in the second terminal run `kubectl proxy` (it lends you kubectl's credentials on port 8001), then:

```bash
curl localhost:8001/api/v1/namespaces/default/pods
curl localhost:8001/apis/apps/v1/namespaces/default/deployments/demo
```

Note the two URL prefixes, `/api/v1` and `/apis/apps/v1` — those are the `apiVersion` values from your manifests. Ctrl+C the proxy when done.

**Check:** you fetched the `demo` Deployment with `curl` and found `"replicas"` in the JSON.

#### D6. DNS names, long and short

From inside the app Pod (`getent` asks the system resolver, the same way the app does):

```bash
kubectl exec <pod> -- cat /etc/resolv.conf
kubectl exec <pod> -- getent hosts demo
kubectl exec <pod> -- getent hosts redis.default.svc.cluster.local
kubectl exec <pod> -- getent hosts kube-dns.kube-system
```

```
search default.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.43.0.10
options ndots:5
10.43.47.231    demo.default.svc.cluster.local
10.43.24.110    redis.default.svc.cluster.local
10.43.0.10      kube-dns.kube-system.svc.cluster.local
```

Every Pod's `resolv.conf` points at CoreDNS (10.43.0.10 = the `kube-dns` Service) with a `search` list that turns `demo` into `demo.default.svc.cluster.local`. That's why the short name works within a namespace and `kube-dns.kube-system` is needed across one.

**Check:** `demo` and its full name resolve to the same ClusterIP.

### Tier 3 — challenges

#### D7. NodePort: the second way in

Change `k8s/service.yaml` to `type: NodePort`, apply, `kubectl get service demo` and find the assigned port in `PORT(S)` (`80:31528/TCP` — the second number, from the 30000–32767 range). Now reach it: on k3d the "node" is a container, so the port is open *inside* Docker's network, not on your laptop. Find the node's IP with `docker network inspect k3d-cos` (look for `k3d-cos-server-0`), then `curl <that ip>:<nodeport>/`. Explain why `curl localhost:<nodeport>/` fails and which `k3d cluster create --port` flag would make it work. Change the Service back to `ClusterIP` when done.

#### D8. Two containers, one Pod

Add a second container to the demo Pod template: `image: alpine:3.20`, `command: ["sh", "-c", "while true; do wget -qO- http://localhost:8000/hostname; sleep 5; done"]`. Apply, `kubectl logs <pod> -c <sidecar name>`. It reaches the app on **localhost** — same net namespace, shared IP, one Pod. Then `kubectl get pods`: what does `2/2` mean? Remove it afterwards.

#### D9. Make Redis persist on Kubernetes

Items in the k3d cluster die with the Redis Pod (`kubectl delete pod <redis pod>`, then `GET /items`). Fix it with the smallest change you can find: read *kubernetes.io → Volumes → emptyDir* and *hostPath*, add one to `redis.yaml` mounted at `/data`, and test again with a Pod delete. Then answer: which one survives a Pod delete? A node delete (`k3d cluster delete` + create)? What would a real cluster need instead? (That's a PersistentVolumeClaim — Week 3.)

---

## Appendix — other online clusters

If iximiuz Labs is unavailable, these also give you a Kubernetes cluster in the browser:

| Service | Address | Pick |
|---|---|---|
| Killercoda | https://killercoda.com/playgrounds | Kubernetes |
| KodeKloud | https://kodekloud.com/playgrounds | Kubernetes single-node (latest) |

Neither has Docker next to the cluster nor a registry, so you **cannot build your own image there**. Do Steps 1–3 on a machine with Docker, and in `k8s/deployment.yaml` use a public image name from the instructor instead of `demo:v1`. Everything from Step 6 on then works the same. Ask before the lab if you plan to use one of these.
