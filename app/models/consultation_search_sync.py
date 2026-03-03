from typing import Optional
from sqlmodel import Field, Column, BigInteger, Integer, String, TEXT, ForeignKey, SQLModel
from sqlalchemy.dialects.mysql import TIMESTAMP
from datetime import datetime
from app.models.enums import IndexStatus


class ConsultationSearchSync(SQLModel, table=True):
    """상담 검색 동기화 모델."""
    __tablename__ = "consultation_search_sync"
    
    doc_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    
    consultation_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("consultations.consultation_id"),
            unique=True,
            nullable=True
        )
    )
    
    index_alias: str = Field(
        default="consultations_histories",
        max_length=255
    )
    
    es_doc_id: str = Field(max_length=255)
    index_status: IndexStatus = Field(default=IndexStatus.PENDING)
    
    source_updated_at: datetime = Field(default_factory=datetime.now)
    last_indexed_at: Optional[datetime] = Field(default_factory=datetime.now)
    last_attempt_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    retry_count: int = Field(default=0)
    
    last_error: Optional[str] = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True)
    )
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
