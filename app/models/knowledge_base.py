from typing import Optional
from sqlmodel import Field, Column, BigInteger, TEXT, SQLModel
from datetime import datetime

class KnowledgeBase(SQLModel, table=True):
    """지식 베이스(KB) 기본 모델"""
    __tablename__ = "knowledge_base"

    kb_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )

    faq_id: Optional[str] = Field(
        default=None,
        max_length=55
    )
    
    product_line_code: Optional[str] = Field(
        default=None, 
        max_length=255, 
    )
    
    request: Optional[str] = Field(
        default=None, 
        sa_column=Column(TEXT)
    )
    
    answer: Optional[str] = Field(
        default=None, 
        sa_column=Column(TEXT)
    )
    
    hit_count: Optional[int] = Field(
        default=0,
        sa_column=Column(BigInteger, default=0)
    )
    
    last_hit_at: Optional[datetime] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)