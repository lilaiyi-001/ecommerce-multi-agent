"""FastAPI application entry point"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.intent import router as intent_router
from app.api.orchestrator import router as orch_router
from app.api.selection import router as selection_router
from app.api.trend import router as trend_router
from app.api.profile import router as profile_router
from app.api.competitor import router as competitor_router
from app.api.pricing import router as pricing_router
from app.api.copy import router as copy_router
from app.api.inventory import router as inventory_router
from app.api.promotion import router as promotion_router
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.products import router as products_router
from app.api.reports import router as reports_router
from app.agents import register_all_agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    register_all_agents()
    yield


from app.utils.error_handler import ErrorHandlingMiddleware
from app.utils.logging_config import setup_logging
from app.utils.rate_limiter import RateLimitMiddleware
from app.utils.auth import require_auth
from fastapi import Depends


app = FastAPI(
    title="Ecommerce Multi-Agent System",
    description="LangGraph-based multi-agent collaboration platform for ecommerce selection",
    version="0.2.0",
    lifespan=lifespan,
)

setup_logging()

app.add_middleware(ErrorHandlingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)

app.include_router(intent_router)
app.include_router(orch_router)
app.include_router(selection_router)
app.include_router(trend_router)
app.include_router(profile_router)
app.include_router(competitor_router)
app.include_router(pricing_router)
app.include_router(copy_router)
app.include_router(inventory_router)
app.include_router(promotion_router)
app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(reports_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Ecommerce Multi-Agent System", "version": "0.2.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}

