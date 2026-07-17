
"""日志配置 — RotatingFileHandler，支持按大小轮转

职责：
- 同时输出到控制台（StreamHandler）和文件（RotatingFileHandler）
- 文件按大小轮转：默认 10MB × 5 个备份
- 启动时不覆盖历史日志（append 模式）
- 所有模块通过 logging.getLogger(__name__) 自动继承此配置
"""
from __future__ import annotations
import logging
import logging.handlers
import os
from app.config import settings


def setup_logging():
    """初始化全局日志配置，在应用启动时调用一次"""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_file = settings.LOG_FILE
    max_bytes = settings.LOG_MAX_BYTES
    backup_count = settings.LOG_BACKUP_COUNT

    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # 清除已有 handler，避免重复（uvicorn 可能已添加）
    root.handlers.clear()

    # 控制台输出
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 文件输出（RotatingFileHandler）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 抑制第三方库的 DEBUG 日志噪音
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "日志初始化完成: level=%s file=%s max_bytes=%d backup_count=%d",
        settings.LOG_LEVEL, log_file, max_bytes, backup_count,
    )
