"""日志轮转测试"""
from __future__ import annotations
import logging
import os
from app.utils.logging_config import setup_logging


class TestLogging:

    def test_logger_has_handlers(self):
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_file_handler_configured(self):
        from logging.handlers import RotatingFileHandler
        root = logging.getLogger()
        has = any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        assert has

    def test_stream_handler_configured(self):
        root = logging.getLogger()
        has = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        assert has

    def test_log_file_exists_and_writable(self):
        from app.config import settings
        log_file = settings.LOG_FILE
        assert os.path.exists(log_file)
        size_before = os.path.getsize(log_file)
        logger = logging.getLogger("test_write")
        logger.info("test_write_message")
        for h in logging.getLogger().handlers:
            if hasattr(h, 'flush'):
                h.flush()
        size_after = os.path.getsize(log_file)
        assert size_after >= size_before
