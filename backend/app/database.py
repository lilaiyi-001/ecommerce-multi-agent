"""数据库引擎与会话管理"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# SQLite 需要 check_same_thread=False
_connect_args = {}
_extra_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
else:
    # PostgreSQL 才支持连接池
    _extra_kwargs["pool_size"] = 5
    _extra_kwargs["max_overflow"] = 10

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    **_extra_kwargs,
)

# SQLite 启用 WAL 模式提升并发性能
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表（开发环境用，生产用 alembic 迁移）"""
    import app.models  # noqa: F401 — 确保所有模型被加载
    Base.metadata.create_all(bind=engine)
