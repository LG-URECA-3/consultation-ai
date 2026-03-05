"""Elasticsearch faq_knowledge_base 인덱스 문서 스키마."""
from typing import Any
from pydantic import BaseModel, Field

from app.models.enums import ProductLineCode


class FaqDoc(BaseModel):
    """faq_knowledge_base 인덱스에 저장할 FAQ 문서 형식."""

    faq_id: str
    source_consultation_id: str
    question: str
    answer: str
    question_vector: list[float] = Field(default_factory=list)
    product_line_code: ProductLineCode
    hit_count: int = 1
    created_at: str = ""

    model_config = {"extra": "forbid"}


    def to_es_body(self) -> dict[str, Any]:
        """ES index API body로 직렬화."""
        return {
            "faq_id": self.faq_id,
            "source_consultation_id": self.source_consultation_id,
            "question": self.question,
            "answer": self.answer,
            "question_vector": self.question_vector,
            "product_line_code": self.product_line_code.value,
            "hit_count": self.hit_count,
            "created_at": self.created_at,
        }
