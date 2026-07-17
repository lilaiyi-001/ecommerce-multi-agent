
"""令牌桶限流中间件 — 纯 Python 实现，无外部依赖

基于 IP + 时间窗口的令牌桶算法：
- 每个 IP 在窗口期内拥有固定数量的令牌
- 每次请求消耗一个令牌，令牌耗尽返回 429
- 窗口过期后自动重置
"""
from __future__ import annotations
import time
import threading
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


class TokenBucket:
    """单个 IP 的令牌桶"""

    def __init__(self, max_tokens: int, window_seconds: int):
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds
        self.tokens = max_tokens
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed >= self.window_seconds:
            self.tokens = self.max_tokens
            self.last_refill = now

    def consume(self) -> bool:
        self._refill()
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 IP 的令牌桶限流中间件"""

    WHITELIST = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/api/v1/auth/login", "/api/v1/auth/verify"}


    @classmethod
    def reset_all_buckets(cls):
        """重置所有 IP 的令牌桶（仅用于测试）"""
        for mw in cls._instances:
            mw._buckets.clear()

    _instances: list = []

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        RateLimitMiddleware._instances.append(self)


    def _get_bucket(self, ip: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(ip)
            if bucket is None or bucket.max_tokens != self.max_requests:
                bucket = TokenBucket(self.max_requests, self.window_seconds)
                self._buckets[ip] = bucket
            return bucket

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.WHITELIST:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        bucket = self._get_bucket(ip)

        if not bucket.consume():
            retry_after = self.window_seconds
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
