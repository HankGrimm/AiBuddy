from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .core.database import engine, Base
from .middleware.x402_payment import _X402Exception

# Import all models to ensure they're registered
from .models import *  # noqa

from .api import (
    users, personas, rooms, stakes, matches,
    attestations, social_reputation, safety, match_agent,
    nfts, transfers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic migrations in production)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Monad Mate — Social trust backend: stake-to-interact, AI matchmaking, meetup attestations, safety escrow",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(_X402Exception)
async def x402_exception_handler(request: Request, exc: _X402Exception):
    """Return the pre-built 402 JSONResponse from the x402 payment dependency."""
    return exc.response

# Register routers
app.include_router(users.router)
app.include_router(personas.router)
app.include_router(rooms.router)
app.include_router(stakes.router)
app.include_router(matches.router)
app.include_router(attestations.router)
app.include_router(social_reputation.router)
app.include_router(safety.router)
app.include_router(match_agent.router)
app.include_router(nfts.router)
app.include_router(transfers.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "service": "Monad Mate Trust API",
        "docs": "/docs",
        "health": "/health",
    }
