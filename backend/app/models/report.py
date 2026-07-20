"""报告记录 ORM 模型"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Report(Base):
    """用户生成的选品分析报告"""
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), index=True, nullable=False, comment="会话ID")
    product_ids = Column(JSON, nullable=False, comment="用户选择的商品ID列表")
    activity_type = Column(String(32), nullable=False, comment="活动类型：双11/618/新品发布/清仓/日常促销/自定义")
    category = Column(String(32), nullable=True, comment="分析类目")
    summary = Column(Text, nullable=True, comment="报告摘要")
    report_content = Column(JSON, nullable=False, comment="完整报告内容JSON")
    created_at = Column(DateTime, default=_utcnow, index=True)

    def __repr__(self):
        return f"<Report {self.id} activity={self.activity_type} products={len(self.product_ids)}>"
