# API Mawjoud
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from routers import admin, points, signalements


@asynccontextmanager
async def lifespan(app):
    init_db()  # tables + seed au démarrage
    yield


app = FastAPI(title="Mawjoud", lifespan=lifespan)

# CORS ouvert (front sur Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(points.router)
app.include_router(signalements.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"ok": True}
