"""상담 이력 ES 인덱싱 API."""
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.infrastructure import get_session
from app.schemas.consultation_history_es import (
    ConsultationHistorySearchRequest,
    ConsultationHistorySearchResponse,
)
from app.services.processor.post_processor import (
    post_processing,
)
from app.services.processor.consultation_history_search import search_by_summary
from app.schemas.consultation_history_doc import ConsultationHistoryDoc

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
    doc = await post_processing(consultation_id)
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





from pydantic import BaseModel, Field
from app.services.common.embeddings import get_embedding
from app.services.processor.es_faq import faq_similarity_search
from loguru import logger
from app.models.enums import ProductLineCode

class FAQSearchTestRequest(BaseModel):
    summary_text: str = Field(..., description="검색할 요약문 (임베딩 후 kNN 검색에 사용)")
    product_line_code: ProductLineCode = Field(..., description="상품군 코드")
    keywords: list[str] = Field(..., description="키워드 리스트")


@router.post("/faq-similarity")
async def test_faq_similarity(request: FAQSearchTestRequest):
    """
    현재 구현된 하이브리드 검색 로직을 수동으로 테스트합니다.
    """
    try:
        # Step B: 요약문에 대한 벡터 생성 (512차원)
        summary_vector = await get_embedding(request.summary_text)

        # Step C: 이전에 작성한 하이브리드 검색 함수 호출
        # (앞서 정의한 faq_similarity_search 함수가 같은 파일 혹은 import 가능해야 함)

        return await faq_similarity_search(
            summary_vector=summary_vector,
            keywords=request.keywords,
            product_line_code=request.product_line_code.value
        )

    except Exception as e:
        logger.error(f"테스트 중 에러 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))