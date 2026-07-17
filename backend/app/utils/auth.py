"""JWT 鉴权工具模块"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status, Request
import jwt as pyjwt
from app.config import settings

logger = logging.getLogger(__name__)


def create_access_token(username: str) -> str:
    """生成 JWT access token"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "iat": now, "exp": expire, "type": "access"}
    return pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """验证 JWT token，返回 payload"""
    try:
        return pyjwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期，请重新登录")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")


def require_auth(request: Request) -> str:  # 同步版本，兼容 sync 路由
    """FastAPI 依赖注入：从请求头中提取并验证 token"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证 Token")
    token = auth[7:]
    payload = verify_token(token)
    return payload.get("sub", "unknown")


class SimpleAuthMiddleware:
    """简单 ASGI 鉴权中间件：保护 /api/v1/ 下的所有路由（排除 auth/login）"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # 公开路径放行
        if method == "OPTIONS" or path in ("/", "/health") or path.startswith(("/docs", "/redoc", "/openapi.json", "/api/v1/auth/login")):
            await self.app(scope, receive, send)
            return

        # 只有 /api/v1/ 下的路由需要鉴权
        if path.startswith("/api/v1/"):
            headers = dict(scope.get("headers", []))
            auth_header = ""
            for k, v in headers:
                if k == b"authorization":
                    auth_header = v.decode("utf-8", errors="replace")
                    break
            if not auth_header.startswith("Bearer "):
                return await _send_json(send, 401, {"detail": "未提供认证 Token"})
            try:
                verify_token(auth_header[7:])
            except HTTPException:
                return await _send_json(send, 401, {"detail": "Token 无效或已过期"})

        await self.app(scope, receive, send)


async def _send_json(send, status_code: int, data: dict):
    import json
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": status_code, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})
