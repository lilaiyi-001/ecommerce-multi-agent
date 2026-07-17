
"""全局异常处理中间件

职责：
- 捕获所有未处理异常，记录完整上下文（stack trace + request info）
- 返回统一 JSON 错误响应，绝不泄漏内部细节
- 区分 4xx（客户端错误）和 5xx（服务端错误）
"""
from __future__ import annotations
import logging
import traceback
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """全局异常捕获 + 结构化日志"""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed_ms = (time.monotonic() - start) * 1000
            # 正常请求不记录，避免日志噪音
            if response.status_code >= 400:
                logger.warning(
                    "HTTP %d %s %s %.0fms",
                    response.status_code, request.method, request.url.path, elapsed_ms,
                )
            return response
        except StarletteHTTPException as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "HTTP %d %s %s %.0fms | detail=%s",
                e.status_code, request.method, request.url.path, elapsed_ms, e.detail,
            )
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": str(e.detail), "path": request.url.path},
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            tb = traceback.format_exc()
            logger.error(
                "UNHANDLED %s %s %.0fms | %s: %s\n%s",
                request.method, request.url.path, elapsed_ms,
                type(e).__name__, e, tb,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "服务器内部错误，已记录日志",
                    "error_id": f"{int(start * 1000)}-{request.url.path.replace('/', '-')}",
                },
            )
