"""demo-app — the one application this course grows week by week.

Week 2 state: the Week 1 endpoints plus a Redis-backed item list (/items)
and /hostname for watching load-balancing across replicas.
Configuration comes from environment variables only (12-factor style).
"""

import logging
import os
import socket
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

APP_VERSION = os.getenv("APP_VERSION", "dev")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# int() here on purpose: a non-numeric REDIS_PORT crashes the process at import
# time, which is the "CrashLoopBackOff from a bad env var" drill in the W2 lab.
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

ITEMS_KEY = "items"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("demo-app")

# redis-py connects lazily: creating the client never fails, the first command
# does. Every request that needs Redis goes through require_redis() below.
rdb = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("demo-app %s starting on %s", APP_VERSION, socket.gethostname())
    log.info("redis target: %s:%d", REDIS_HOST, REDIS_PORT)
    yield
    log.info("demo-app %s shutting down", APP_VERSION)


app = FastAPI(title="demo-app", version=APP_VERSION, lifespan=lifespan)


class Item(BaseModel):
    name: str


def require_redis() -> redis.Redis:
    """Fail loudly (503) with the target host:port so a wrong REDIS_HOST is obvious."""
    try:
        rdb.ping()
    except redis.exceptions.RedisError as exc:
        log.error("redis unreachable at %s:%d: %s", REDIS_HOST, REDIS_PORT, exc)
        raise HTTPException(
            status_code=503,
            detail=f"redis unreachable at {REDIS_HOST}:{REDIS_PORT}: {exc}",
        )
    return rdb


@app.get("/")
def root():
    """Hello + version + hostname. Hostname = container ID inside Docker."""
    return {
        "message": f"Hello from demo-app {APP_VERSION}",
        "version": APP_VERSION,
        "hostname": socket.gethostname(),
    }


@app.get("/health")
def health():
    """Liveness probe target (used by Kubernetes in Week 3). Always 200 for now.

    Deliberately does NOT check Redis: a liveness probe answers "should I be
    restarted?", and restarting the app doesn't fix a dead Redis.
    """
    return {"status": "ok"}


@app.get("/version")
def version():
    """Returns APP_VERSION — proves that config reaches the container via env."""
    return {"version": APP_VERSION}


@app.get("/hostname")
def hostname():
    """Container ID (Docker) or Pod name (Kubernetes). Loop this to see load-balancing."""
    return {"hostname": socket.gethostname()}


@app.get("/items")
def list_items():
    """All items, oldest first. Lives in Redis, so it survives app restarts."""
    r = require_redis()
    return {"items": r.lrange(ITEMS_KEY, 0, -1)}


@app.post("/items", status_code=201)
def add_item(item: Item):
    """Append one item: POST /items {"name": "milk"}."""
    r = require_redis()
    r.rpush(ITEMS_KEY, item.name)
    log.info("added item %r", item.name)
    return {"added": item.name}


@app.delete("/items")
def clear_items():
    """Wipe the list — handy between demos."""
    r = require_redis()
    r.delete(ITEMS_KEY)
    return {"items": []}
