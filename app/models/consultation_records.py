from typing import Optional
from sqlmodel import Field, Column, BigInteger, TEXT
from app.schemas.base.base_consultation_records import ConsultationRecordBase
from datetime import datetime

# ConsultationRecordBase 상속
class ConsultationRecords(ConsultationRecordBase, table=True):
    """상담 기록 모델. ConsultationRecordBase 상속"""
    __tablename__ = "consultation_records"
    record_id: Optional[int] = Field(
        default=None, 
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )

    customer_request: Optional[str] = Field(sa_column=Column(TEXT))
    agent_action: Optional[str] = Field(sa_column=Column(TEXT))
    summary_text: str = Field(sa_column=Column(TEXT, nullable=False))

    finalized_by: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    finalized_at: Optional[datetime] = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)