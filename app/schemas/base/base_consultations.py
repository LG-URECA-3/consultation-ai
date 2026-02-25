from typing import Optional
from sqlmodel import SQLModel
from datetime import datetime
from app.models.enums import ChannelCode, ProductLineCode, FinalResultCode


class ConsultationBase(SQLModel):
    """공통 상담 기본 정보 스키마"""
    # NN 처리
    customer_id: Optional[int] = None
    agent_id: Optional[int] = None

    # 상담 메타데이터
    channel_code: ChannelCode
    product_line_code: ProductLineCode
    final_result_code: Optional[FinalResultCode] = None

    # 시간 정보
    started_at: datetime
    ended_at: Optional[datetime] = None

