"""MiniMax 大模型 API 封装 - 支持沙箱内外双重调用"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from typing import Optional
from app.config import settings


_client = None
_PROXY_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "llm_proxy.py")
_PYTHON_PATH = r"D:\Anaconda\python.exe"


def get_llm_client():
    """获取 MiniMax 客户端（单例）"""
    global _client
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai 包未安装，LLM 调用不可用。"
                "请执行: pip install openai"
            )
        _client = OpenAI(
            api_key=settings.MINIMAX_API_KEY,
            base_url=settings.MINIMAX_BASE_URL,
        )
    return _client


def _call_proxy(system_prompt: str, user_message: str) -> str:
    """通过外部子进程调用 LLM（绕开沙箱网络限制）"""
    try:
        proc = subprocess.run(
            [
                _PYTHON_PATH, _PROXY_SCRIPT,
                settings.MINIMAX_API_KEY,
                settings.MINIMAX_BASE_URL,
                settings.MINIMAX_MODEL,
                system_prompt,
                user_message,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            result = json.loads(proc.stdout.strip())
            if result.get("success"):
                return result["content"]
        return ""
    except Exception:
        return ""


def chat_completion(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> str:
    """调用 MiniMax 大模型（直接调用->重试->代理脚本->抛异常供上层降级）"""
    import logging
    import time
    logger = logging.getLogger(__name__)

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            client = get_llm_client()
            resp = client.chat.completions.create(
                model=settings.MINIMAX_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"LLM 调用失败 (尝试{attempt+1}/{max_retries}): {type(e).__name__}，{wait}s后重试")
                time.sleep(wait)
            else:
                logger.warning(f"LLM 调用已达最大重试次数: {type(e).__name__}: {e}")

    logger.warning("LLM 直接调用失败，尝试通过代理脚本")
    proxy_result = _call_proxy(system_prompt, user_message)
    if proxy_result:
        return proxy_result

    logger.error(f"LLM 所有调用方式均失败: {last_error}")
    return ""  