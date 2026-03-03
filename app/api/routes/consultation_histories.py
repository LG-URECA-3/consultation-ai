"""상담 이력 ES 인덱싱 API."""
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.infrastructure import get_session
from app.schemas.consultation_history_es import (
    ConsultationHistorySearchRequest,
    ConsultationHistorySearchResponse,
)
from app.services.post_processor import (
    post_processing,
)
from app.services.consultation_history_search import search_by_summary
from app.schemas.consultation_search_index import ConsultationHistoryDoc

router = APIRouter(prefix="/consultation-histories", tags=["consultation-histories"])


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: DB 세션."""
    async for session in get_session():
        yield session


@router.post(
    "/index/{consultation_id}",
    response_model=ConsultationHistoryDoc,
    summary="상담 이력 ES 인덱싱",
    description="consultation_id로 DB를 조회해 consultation_histories 인덱스에 저장합니다.",
)
async def index_consultation_to_es(
    consultation_id: int,
    db: AsyncSession = Depends(get_db),
) -> ConsultationHistoryDoc:
    doc = await post_processing(db, consultation_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return doc


@router.post(
    "/search",
    response_model=ConsultationHistorySearchResponse,
    summary="요약문 유사도 검색",
    description="요약문 하나를 받아 임베딩 후 consultation_histories에서 유사한 상담 이력을 검색합니다.",
)
async def search_consultation_histories(
    body: ConsultationHistorySearchRequest,
) -> ConsultationHistorySearchResponse:
    hits = await search_by_summary(
        summary_text=body.summary_text,
        k=body.k,
    )
    max_score = max((h.score for h in hits), default=None)
    return ConsultationHistorySearchResponse(hits=hits, max_score=max_score)
