"""FastAPI 应用入口"""
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
from app.agents import register_all_agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    register_all_agents()
    yield


from app.utils.error_handler import ErrorHandlingMiddleware
from app.utils.logging_config import setup_logging
from app.utils.rate_limiter import RateLimitMiddleware
from app.utils.auth import require_auth
from fastapi import Depends


app = FastAPI(
    title="电商选品运营多智能体系统",
    description="基于 LangGraph 的多智能体协作平台",
    version="0.1.0",
    lifespan=lifespan,
)

setup_logging()

# 全局异常处理中间件（最外层，捕获所有未处理异常）
app.add_middleware(ErrorHandlingMiddleware)

# 公开路由不需要鉴权（auth/login 内部已排除）
# 所有 /api/v1/ 路由通过 require_auth 依赖保护
# 具体路由在各自的 router 中通过 Depends(require_auth) 添加

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求限流中间件（令牌桶，默认 30次/60秒/IP，/ 和 /health 白名单不限流）
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)




# 注册路由
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


@app.get("/")
def root():
    return {"status": "ok", "service": "电商选品运营多智能体系统", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
