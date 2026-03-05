from __future__ import annotations
from app.schemas.consultation_history_doc import ConsultationHistoryDoc
from app.services.consultation_history_indexer import fetch_and_index_consultation_history
from app.services.faq_indexer import run_faq_from_consultation_doc

async def post_processing(
    consultation_id: int,
) -> ConsultationHistoryDoc | None:
    """후처리 과정의 메인 흐름: 
    Step 1: consultation_id 기준 상담 이력 조회·ES 인덱싱. DB에 상담이 없으면 None 반환.
    Step 2: FAQ 매칭/생성 (요약문 기준 hit_count 증가 또는 신규 FAQ 인덱싱)
    Step 3: 고객 성향 분석
    """

    # Step 1: 상담 데이터 조회·가공·ES 인덱싱
    doc = await fetch_and_index_consultation_history(consultation_id)
    if doc is None:
        return None

    # Step 2: FAQ 매칭/생성 (요약문 기준 hit_count 증가 또는 신규 FAQ 인덱싱)
    await run_faq_from_consultation_doc(doc)

    return doc

    # Step 3: 고객 성향 분석
    # 구현 예정