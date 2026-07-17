"""对话记录ORM模型"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Conversation(Base):
    """用户对话记录"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), index=True, nullable=False, comment="会话ID")
    user_id = Column(String(64), nullable=True, comment="飞书用户ID，未登录用户为空")
    turn_number = Column(Integer, default=1, comment="当前轮次")
    role = Column(String(16), nullable=False, comment="user 或 assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    metadata_json = Column(JSON, nullable=True, comment="附加元数据")
    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<Conversation {self.session_id} turn={self.turn_number} role={self.role}>"
