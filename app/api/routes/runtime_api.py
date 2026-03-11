from fastapi import APIRouter
from app.services.rumtime.runtime_search import runtime_search

router = APIRouter(prefix="/api/v1", tags=["runtime-api"])

@router.post(
    "/search/faq",
    response_model=str,
    summary="실시간 faq 검색 및 답변 추출",
    description="question_text를 임베딩 후 consultation_histories 인덱스에서 유사도 검색합니다. 유사도에 따라 답변을 추출하여 반환합니다.",
)
async def search_runtime(consultationId: int, question_text: str):
    return await runtime_search(question_text)