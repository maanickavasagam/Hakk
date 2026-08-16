from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import auth, cases, documents, meta, payments
from .services import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Hakk API",
    description="Autonomous consumer-dispute resolution agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(payments.router)
app.include_router(meta.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "hakk"}
