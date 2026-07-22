"""全局配置模块 - 纯 Python 实现，无外部依赖"""
import os
import sys
from pathlib import Path
from typing import Optional

# 将 lib 目录加入 sys.path（安装的第三方包在 lib/ 下）
_lib_path = str(Path(__file__).parent.parent / "lib")
if os.path.isdir(_lib_path) and _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)


def _load_env():
    """手动加载 .env 文件（不用 python-dotenv 或 pydantic-settings）"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                for ch in ('"', "'"):
                    if val.startswith(ch) and val.endswith(ch):
                        val = val[1:-1]
                        break
                os.environ.setdefault(key, val)


_load_env()


class Settings:
    """全局配置 - 从 .env 文件和 os.environ 加载"""

    @property
    def MINIMAX_API_KEY(self) -> str:
        return os.getenv("MINIMAX_API_KEY", "")

    @property
    def MINIMAX_BASE_URL(self) -> str:
        return os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")

    @property
    def MINIMAX_MODEL(self) -> str:
        return os.getenv("MINIMAX_MODEL", "minimax-m3")

    @property
    def FEISHU_APP_ID(self) -> str:
        return os.getenv("FEISHU_APP_ID", "")

    @property
    def FEISHU_APP_SECRET(self) -> str:
        return os.getenv("FEISHU_APP_SECRET", "")

    @property
    def FEISHU_BITABLE_APP_TOKEN(self) -> str:
        return os.getenv("FEISHU_BITABLE_APP_TOKEN", "")

    @property
    def FEISHU_BITABLE_TABLE_ID(self) -> str:
        return os.getenv("FEISHU_BITABLE_TABLE_ID", "")

    @property
    def FEISHU_BITABLE_VIEW_ID(self) -> str:
        return os.getenv("FEISHU_BITABLE_VIEW_ID", "")

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///./ecommerce_selection.db")

    @property
    def JWT_SECRET_KEY(self) -> str:
        return os.getenv("JWT_SECRET_KEY", "change-this-to-a-secure-key")

    @property
    def JWT_ALGORITHM(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def JWT_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    @property
    def AUTH_USERNAME(self) -> str:
        return os.getenv("AUTH_USERNAME", "admin")

    @property
    def AUTH_PASSWORD(self) -> str:
        return os.getenv("AUTH_PASSWORD", "admin123")

    @property
    def SERVER_HOST(self) -> str:
        return os.getenv("SERVER_HOST", "0.0.0.0")

    @property
    def SERVER_PORT(self) -> int:
        return int(os.getenv("SERVER_PORT", "8000"))

    @property
    def FEISHU_REDIRECT_URI(self) -> str:
        return os.getenv("FEISHU_REDIRECT_URI", "http://localhost:8000/api/v1/auth/callback")

    @property
    def CHROMA_DB_PATH(self) -> str:
        return os.getenv("CHROMA_DB_PATH", str(Path(__file__).parent.parent / "chroma_db"))

    @property
    def LOG_LEVEL(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")



    @property
    def RATE_LIMIT_MAX_REQUESTS(self) -> int:
        return int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))

    @property
    def RATE_LIMIT_WINDOW_SECONDS(self) -> int:
        return int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))


    @property
    def LOG_FILE(self) -> str:
        return os.getenv("LOG_FILE", str(Path(__file__).parent.parent / "server.log"))

    @property
    def LOG_MAX_BYTES(self) -> int:
        return int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))

    @property
    def LOG_BACKUP_COUNT(self) -> int:
        return int(os.getenv("LOG_BACKUP_COUNT", "5"))
    # ═══════ 飞书库存表格配置 ═══════
    @property
    def FEISHU_INVENTORY_APP_ID(self) -> str:
        return os.getenv("FEISHU_INVENTORY_APP_ID", "")

    @property
    def FEISHU_INVENTORY_APP_SECRET(self) -> str:
        return os.getenv("FEISHU_INVENTORY_APP_SECRET", "")

    @property
    def FEISHU_INVENTORY_BITABLE_APP_TOKEN(self) -> str:
        return os.getenv("FEISHU_INVENTORY_BITABLE_APP_TOKEN", "")

    @property
    def FEISHU_INVENTORY_TABLE_ID(self) -> str:
        return os.getenv("FEISHU_INVENTORY_TABLE_ID", "")

    @property
    def FEISHU_INVENTORY_VIEW_ID(self) -> str:
        return os.getenv("FEISHU_INVENTORY_VIEW_ID", "")

    # ═══════ 飞书爬取商品数据表格配置 ═══════
    @property
    def FEISHU_CRAWLED_APP_ID(self) -> str:
        return os.getenv("FEISHU_CRAWLED_APP_ID", "")

    @property
    def FEISHU_CRAWLED_APP_SECRET(self) -> str:
        return os.getenv("FEISHU_CRAWLED_APP_SECRET", "")

    @property
    def FEISHU_CRAWLED_BITABLE_APP_TOKEN(self) -> str:
        return os.getenv("FEISHU_CRAWLED_BITABLE_APP_TOKEN", "")

    @property
    def FEISHU_CRAWLED_TABLE_ID(self) -> str:
        return os.getenv("FEISHU_CRAWLED_TABLE_ID", "")

    @property
    def FEISHU_CRAWLED_VIEW_ID(self) -> str:
        return os.getenv("FEISHU_CRAWLED_VIEW_ID", "")


settings = Settings()
os.environ.setdefault("OPENAI_API_KEY", settings.MINIMAX_API_KEY)
