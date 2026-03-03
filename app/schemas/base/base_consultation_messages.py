from sqlmodel import SQLModel
from app.models.enums import SenderType
from typing import Optional

class ConsultationMessageBase(SQLModel):
    """공통 상담 메시지 스키마"""
    message_seq: int
    sender_type: Optional[SenderType] = None
    content: str