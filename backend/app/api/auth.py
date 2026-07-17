"""用户认证 API 路由 — 登录获取 JWT Token"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.config import settings
from app.utils.auth import create_access_token, require_auth

router = APIRouter(prefix="/api/v1/auth", tags=["用户认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
def login(input_data: LoginRequest):
    """用户登录：验证用户名密码，返回 JWT Token"""
    auth_username = settings.AUTH_USERNAME
    auth_password = settings.AUTH_PASSWORD

    if not auth_username or not auth_password:
        raise HTTPException(status_code=500, detail="服务端未配置认证信息")

    if input_data.username != auth_username or input_data.password != auth_password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(input_data.username)
    return LoginResponse(access_token=token, username=input_data.username)


@router.get("/verify")
def verify_token(username: str = Depends(require_auth)):  # 同步版本
    """验证当前 token 是否有效"""
    return {"status": "ok", "username": username}
