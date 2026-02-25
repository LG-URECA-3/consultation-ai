from sqlmodel import SQLModel
from typing import Optional

class ConsultationRecordBase(SQLModel):
    """공통 상담 기록 스키마"""
    consultation_id: int
    summary_text: str