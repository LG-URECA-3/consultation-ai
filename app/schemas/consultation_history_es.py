"""Elasticsearch consultation_histories 인덱스 문서 스키마."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- 검색 API용 스키마 ---


class ConsultationHistorySearchRequest(BaseModel):
    """요약문 유사도 검색 요청."""
    summary_text: str = Field(..., description="검색할 요약문 (임베딩 후 kNN 검색에 사용)")
    k: int = Field(default=10, ge=1, le=100, description="반환할 유사 상담 이력 개수")


class ConsultationHistorySearchHitMetadata(BaseModel):
    """검색 결과용 메타데이터 (ES 저장값 그대로 사용)."""
    agent_id: str = ""
    customer_id: str = ""
    category: str = ""
    resolution_code: str = ""
    start_time: str | None = None
    end_time: str | None = None


class ConsultationHistorySearchHit(BaseModel):
    """검색 결과 한 건."""
    consultation_id: str
    summary_text: str
    full_text: str
    metadata: ConsultationHistorySearchHitMetadata
    score: float = Field(..., description="유사도 점수 (코사인 유사도)")


class ConsultationHistorySearchResponse(BaseModel):
    """요약문 유사도 검색 응답."""
    hits: list[ConsultationHistorySearchHit]
    max_score: float | None = Field(
        default=None,
        description="검색 결과 중 최대 유사도 점수 (코사인 유사도)",
    )


class CustomerPersona(BaseModel):
    """고객 페르소나 (감정/특성)."""
    sentiment: str = "NEUTRAL"
    traits: list[str] = Field(default_factory=list)


class ConsultationHistoryMetadata(BaseModel):
    """상담 메타데이터."""
    agent_id: str
    customer_id: str
    category: str
    resolution_code: str
    start_time: datetime
    end_time: datetime | None = None


class ConsultationHistoryDoc(BaseModel):
    """consultation_histories 인덱스에 저장할 문서 형식."""
    consultation_id: str
    full_text: str
    summary_text: str
    summary_vector: list[float] = Field(default_factory=list)
    customer_persona: CustomerPersona = Field(default_factory=CustomerPersona)
    metadata: ConsultationHistoryMetadata

    model_config = {"extra": "forbid"}

    def to_es_body(self) -> dict[str, Any]:
        """ES index API body로 직렬화 (datetime 등 처리)."""
        return {
            "consultation_id": self.consultation_id,
            "full_text": self.full_text,
            "summary_text": self.summary_text,
            "summary_vector": self.summary_vector,
            "customer_persona": self.customer_persona.model_dump(),
            "metadata": {
                "agent_id": self.metadata.agent_id,
                "customer_id": self.metadata.customer_id,
                "category": self.metadata.category,
                "resolution_code": self.metadata.resolution_code,
                "start_time": self.metadata.start_time.isoformat(),
                "end_time": self.metadata.end_time.isoformat() if self.metadata.end_time else None,
            },
        }
