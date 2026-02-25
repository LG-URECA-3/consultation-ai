from typing import Optional
from sqlmodel import Field, Column, BigInteger, Integer, TEXT
from app.schemas.base.base_consultation_messages import ConsultationMessageBase
from datetime import datetime

# ConsultationMessageBase 상속
class ConsultationMessages(ConsultationMessageBase, table=True):
    """상담 메시지 모델. ConsultationMessageBase 상속"""
    __tablename__ = "consultation_messages"
    message_id: Optional[int] = Field(
        default=None, 
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    consultation_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    # base의 content를 TEXT 타입으로 변환
    content: str = Field(sa_column=Column(TEXT, nullable=False))
    sent_at: Optional[datetime] = Field(default_factory=datetime.now)