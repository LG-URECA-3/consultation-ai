from typing import Optional
from sqlmodel import Field, Column, BigInteger, Float, Boolean, ForeignKey, SQLModel
from datetime import datetime
from app.models.enums import AlertLevel

class IssueAlerts(SQLModel, table=True):
    """이슈 스파이크 알림 모델"""
    __tablename__ = "issue_alerts"

    alert_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )

    kb_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("knowledge_base.kb_id"),
            nullable=True
        )
    )

    spike_rate: float = Field(
        sa_column=Column(Float, nullable=False)
    )

    alert_level: AlertLevel = Field(nullable=False)

    is_posted: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False, nullable=False)
    )

    created_at: datetime = Field(default_factory=datetime.now)