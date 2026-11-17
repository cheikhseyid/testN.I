import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .db import Base, engine
from .routers import auth, points, signalements, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Points d'eau API", lifespan=lifespan)

# Rate limiting (slowapi): 429 when a limit is exceeded.
app.state.limiter = signalements.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def parse_origins(raw: str) -> list[str]:
    """CORS_ORIGINS -> exact origins. Tolerates the usual dashboard typos: spaces,
    quotes, a trailing "/" or a path (browsers send the Origin without them)."""
    out = []
    for item in raw.replace(";", ",").replace("\n", ",").split(","):
        o = item.strip().strip("'\"").strip()
        if not o:
            continue
        scheme, sep, rest = o.partition("://")
        o = (scheme.lower() + sep + rest.split("/", 1)[0].lower()) if sep else o.rstrip("/")
        if o not in out:
            out.append(o)
    return out


origins = parse_origins(os.getenv("CORS_ORIGINS", ""))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Compress JSON responses (e.g. /points, /stats, /signalements) when the client accepts gzip.
# Below 500 bytes compression isn't worth it. Images (already JPEG/PNG) gain nothing but are rare.
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(points.router)
app.include_router(signalements.router)
app.include_router(auth.router)
app.include_router(stats.router)
