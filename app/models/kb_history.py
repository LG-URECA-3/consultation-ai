from typing import Optional
from sqlmodel import Field, Column, BigInteger, ForeignKey, SQLModel
from datetime import datetime

class KbHistory(SQLModel, table=True):
    """KB 조회 이력 및 스냅샷 모델"""
    __tablename__ = "kb_history"

    history_id: Optional[int] = Field(
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

    hit_count_snapshot: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger)
    )

    recorded_at: datetime = Field(default_factory=datetime.now)