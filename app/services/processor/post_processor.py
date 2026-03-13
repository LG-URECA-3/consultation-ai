from __future__ import annotations
from app.schemas.consultation_history_doc import ConsultationHistoryDoc
from app.services.processor.consultation_history_indexer import fetch_and_index_consultation_history
from app.services.processor.faq_indexer import run_faq_from_consultation_doc
from app.crud.crud_consultation_record import get_record_id_by_consultation_id
from app.core.infrastructure import AsyncSessionLocal
from loguru import logger
from typing import Optional

async def post_processing(
    consultation_id: int,
    record_id: Optional[int] = None
) -> ConsultationHistoryDoc | None:
    """후처리 과정의 메인 흐름: 
    Step 1: consultation_id 기준 상담 이력 조회·ES 인덱싱. DB에 상담이 없으면 None 반환.
    Step 2: FAQ 매칭/생성 (요약문 기준 hit_count 증가 또는 신규 FAQ 인덱싱)
    Step 3: 고객 성향 분석
    """

    try:
        if record_id is None:
            async with AsyncSessionLocal() as session:
                record_id = await get_record_id_by_consultation_id(session, consultation_id)
                
        # Step 1: 상담 데이터 조회·가공·ES 인덱싱
        doc = await fetch_and_index_consultation_history(consultation_id, record_id)
        if doc is None:
            return None

        # Step 2: FAQ 매칭/생성 (요약문 기준 hit_count 증가 또는 신규 FAQ 인덱싱)
        await run_faq_from_consultation_doc(doc)

        return doc
    except Exception as e:
        logger.error(f"후처리 중 오류 발생: {e}")
        return None