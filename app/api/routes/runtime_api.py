from fastapi import APIRouter, HTTPException
from app.services.rumtime.runtime_search import runtime_search
from app.schemas.runtime_search_resonse import RuntimeSearchResponse
from app.services.processor.consultation_history_search import search_consultations_list
from app.schemas.consultation_history_es import ConsultationSearchRequest, ConsultationSearchResponse
from app.schemas.consultation_detail import ConsultationDetailResponse, ConsultationMessageDetail
from app.services.processor.es_consultation import _get_consultation_doc_from_es, CONSULTATION_HISTORIES_INDEX
from app.core.infrastructure import es_client
from app.crud.crud_consultation_record import get_record_detail_by_consultation_id
from app.crud.crud_customer import get_customer_phone_mask_by_id, get_customer_name_by_id
from app.crud.crud_user import get_user_name_by_id
from app.core.infrastructure import AsyncSessionLocal

router = APIRouter(prefix="/fastapi/v1", tags=["runtime-api"])

@router.post(
    "/search/faq",
    response_model=RuntimeSearchResponse,
    summary="실시간 faq 검색 및 답변 추출",
    description="question_text를 임베딩 후 faq 인덱스에서 유사도 검색합니다. 유사도에 따라 답변을 추출하여 반환합니다.",
)
async def search_runtime(question_text: str):
    response = await runtime_search(question_text)
    return response


@router.post(
    "/search/consultations",
    response_model=ConsultationSearchResponse,
    summary="상담 이력 키워드+필터 검색",
    description="키워드, 담당자, 날짜 범위, 처리 결과 코드를 조합하여 consultation_histories 인덱스에서 상담 이력을 검색합니다.",
)
async def search_consultations(body: ConsultationSearchRequest) -> ConsultationSearchResponse:
    return await search_consultations_list(body)


@router.get(
    "/consultations/{consultation_id}",
    response_model=ConsultationDetailResponse,
    summary="상담 이력 상세 조회",
    description="ES에서 메시지/요약을 가져오고 DB에서 customer_request, agent_action, 고객 연락처, 상담사 이름을 보완하여 반환합니다.",
)
async def get_consultation_detail(consultation_id: int) -> ConsultationDetailResponse:
    # ES에서 raw 문서 조회
    try:
        resp = await es_client.get(index=CONSULTATION_HISTORIES_INDEX, id=str(consultation_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Consultation not found in ES")

    src = resp.get("_source")
    if not src:
        raise HTTPException(status_code=404, detail="Consultation not found in ES")

    meta = src.get("metadata") or {}

    async with AsyncSessionLocal() as session:
        record = await get_record_detail_by_consultation_id(session, consultation_id)
        customer_id = meta.get("customer_id")
        phone_mask = await get_customer_phone_mask_by_id(session, customer_id) if customer_id else None
        customer_name = await get_customer_name_by_id(session, customer_id) if customer_id else None
        agent_name = await get_user_name_by_id(session, meta.get("agent_id")) if meta.get("agent_id") else None

    raw_messages = src.get("messages") or []
    messages = [
        ConsultationMessageDetail(
            message_seq=m.get("message_seq", 0),
            sender_type=m.get("sender_type", "UNKNOWN"),
            content=m.get("content") or "",
        )
        for m in sorted(raw_messages, key=lambda x: x.get("message_seq", 0))
    ]

    return ConsultationDetailResponse(
        consultation_id=src.get("consultation_id", consultation_id),
        started_at=meta.get("started_at"),
        ended_at=meta.get("ended_at"),
        customer_id=meta.get("customer_id"),
        customer_name=customer_name,
        phone_mask=phone_mask,
        agent_id=meta.get("agent_id"),
        agent_name=agent_name,
        product_line_code=meta.get("product_line_code"),
        final_result_code=meta.get("final_result_code"),
        summary_text=src.get("summary_text"),
        customer_request=record.get("customer_request") if record else None,
        agent_action=record.get("agent_action") if record else None,
        messages=messages,
    )