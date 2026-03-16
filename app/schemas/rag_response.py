from pydantic import BaseModel, Field
from typing import List

class RAGResponse(BaseModel):
    answer: str = Field(..., description="조합된 답변 내용")
    referenced_faq_ids: List[str] = Field(..., description="참조한 FAQ의 ID 리스트 (최대 3개)")