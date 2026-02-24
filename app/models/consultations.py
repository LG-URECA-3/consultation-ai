from typing import Optional
from sqlmodel import Field, Column, BigInteger
from app.schemas.base.base_consultations import ConsultationBase
from datetime import datetime
from app.models.enums import StatusCode, PriorityCode

# ConsultationBase 상속
class Consultation(ConsultationBase, table=True):
    """상담 기본 정보 모델. ConsultationBase 상속"""
    __tablename__ = "consultations"
    consultation_id: Optional[int] = Field(
        default=None, 
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    issue_type_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    status_code: StatusCode
    priority_code: Optional[PriorityCode] = None
    parent_consultation_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    view_count: int = Field(default=0)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    