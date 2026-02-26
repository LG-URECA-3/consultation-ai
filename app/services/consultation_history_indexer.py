"""상담 이력을 DB에서 조회해 consultation_histories 인덱스에 저장하는 서비스."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.infrastructure import es_client, openai_client
from app.models.consultation_messages import ConsultationMessages
from app.models.enums import SenderType
from app.crud.crud_consultation import get_consultation_by_id
from app.crud.crud_consultation_message import get_messages_by_consultation_id
from app.crud.crud_consultation_record import get_record_by_consultation_id
from app.schemas.consultation_history_es import (
    ConsultationHistoryDoc,
    ConsultationHistoryMetadata,
    CustomerPersona,
)
from app.services.faq_knowledge_base import (
    HIGH_SIMILARITY_THRESHOLD,
    LOW_SIMILARITY_THRESHOLD,
    create_and_index_faq,
    increment_faq_hit_count,
    llm_same_question,
    search_faq_top1_by_vector,
)

logger = logging.getLogger(__name__)

CONSULTATION_HISTORIES_INDEX = "consultation_histories"


async def build_and_index_consultation_history(
    session: AsyncSession,
    consultation_id: int,
) -> ConsultationHistoryDoc | None:
    """consultation_id 기준 상담 이력 조회·ES 인덱싱 후 FAQ 매칭/생성 수행. DB에 상담이 없으면 None 반환."""

    # Step 1: 상담 데이터 조회·가공·ES 인덱싱
    doc = await fetch_and_index_consultation_history(session, consultation_id)
    if doc is None:
        return None

    # Step 2: FAQ 매칭/생성 (요약문 기준 hit_count 증가 또는 신규 FAQ 인덱싱)
    await run_faq_from_consultation_doc(doc)
    return doc

    # Step 3: 고객 성향 분석
    # 구현 예정


async def fetch_and_index_consultation_history(
    session: AsyncSession,
    consultation_id: int,
) -> ConsultationHistoryDoc | None:
    """
    Step 1: ES 또는 DB에서 상담 데이터를 확보한 뒤 가공·ES 인덱싱하여 ConsultationHistoryDoc 반환.
    ES에 문서가 있으면 인덱싱 없이 doc만 반환. 없으면 DB 조회 후 doc 생성·인덱싱 후 반환.
    """
    try:
        if await es_client.indices.exists(index=CONSULTATION_HISTORIES_INDEX):
            doc_exists = await es_client.exists(
                index=CONSULTATION_HISTORIES_INDEX,
                id=str(consultation_id),
            )
            if doc_exists:
                doc = await _get_consultation_doc_from_es(consultation_id)
                if doc is not None:
                    return doc
    except Exception as e:
        logger.debug("ES consultation_histories 조회 중 예외 (DB 경로로 진행): %s", e)

    consultation = await get_consultation_by_id(session, consultation_id)
    if not consultation:
        return None

    record = await get_record_by_consultation_id(session, consultation_id)
    messages = await get_messages_by_consultation_id(session, consultation_id)

    full_text = _build_full_text(messages)
    summary_text = (record.summary_text if record else "") or ""

    summary_vector: list[float] = []
    if summary_text:
        embed_res = openai_client.embeddings.create(
            input=summary_text,
            model="text-embedding-3-small",
        )
        summary_vector = embed_res.data[0].embedding
        dims = len(summary_vector)
        if not await es_client.indices.exists(index=CONSULTATION_HISTORIES_INDEX):
            await es_client.indices.create(
                index=CONSULTATION_HISTORIES_INDEX,
                mappings={
                    "properties": {
                        "summary_vector": {
                            "type": "dense_vector",
                            "dims": dims,
                            "index": True,
                            "similarity": "cosine",
                        }
                    }
                },
            )

    customer_persona = CustomerPersona(sentiment="NEUTRAL", traits=[])
    metadata = ConsultationHistoryMetadata(
        agent_id=str(consultation.agent_id or ""),
        customer_id=str(consultation.customer_id or ""),
        category=_category_from_consultation(consultation),
        resolution_code=(
            consultation.final_result_code.value
            if consultation.final_result_code
            else "UNKNOWN"
        ),
        start_time=consultation.started_at,
        end_time=consultation.ended_at,
    )

    doc = ConsultationHistoryDoc(
        consultation_id=str(consultation_id),
        full_text=full_text,
        summary_text=summary_text,
        summary_vector=summary_vector,
        customer_persona=customer_persona,
        metadata=metadata,
    )

    await es_client.index(
        index=CONSULTATION_HISTORIES_INDEX,
        id=str(consultation_id),
        document=doc.to_es_body(),
    )
    return doc


async def run_faq_from_consultation_doc(doc: ConsultationHistoryDoc) -> None:
    """
    Step 2: ConsultationHistoryDoc 기준으로 FAQ top1 매칭 후 hit_count 증가 또는 신규 FAQ 생성.
    """
    consultation_id = int(doc.consultation_id) if doc.consultation_id.isdigit() else 0
    await _run_faq_logic(
        consultation_id=consultation_id,
        summary_text=doc.summary_text,
        summary_vector=doc.summary_vector,
        full_text=doc.full_text,
        category=doc.metadata.category,
    )


async def _get_consultation_doc_from_es(consultation_id: int) -> ConsultationHistoryDoc | None:
    """ES consultation_histories에서 consultation_id 문서를 조회해 ConsultationHistoryDoc으로 반환."""
    try:
        resp = await es_client.get(
            index=CONSULTATION_HISTORIES_INDEX,
            id=str(consultation_id),
        )
    except Exception:
        return None
    src = resp.get("_source") or {}
    meta = src.get("metadata") or {}
    start_time_raw = meta.get("start_time")
    end_time_raw = meta.get("end_time")

    def _parse_iso(s: str | None) -> datetime | None:
        if not s:
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    start_time = _parse_iso(start_time_raw) or datetime.now()
    end_time = _parse_iso(end_time_raw)
    persona = src.get("customer_persona") or {}
    return ConsultationHistoryDoc(
        consultation_id=src.get("consultation_id", str(consultation_id)),
        full_text=src.get("full_text", ""),
        summary_text=src.get("summary_text", ""),
        summary_vector=src.get("summary_vector", []),
        customer_persona=CustomerPersona(**(persona if isinstance(persona, dict) else {})),
        metadata=ConsultationHistoryMetadata(
            agent_id=meta.get("agent_id", ""),
            customer_id=meta.get("customer_id", ""),
            category=meta.get("category", ""),
            resolution_code=meta.get("resolution_code", ""),
            start_time=start_time,
            end_time=end_time,
        ),
    )


async def _run_faq_logic(
    consultation_id: int,
    summary_text: str,
    summary_vector: list[float],
    full_text: str,
    category: str,
) -> None:
    """요약문 벡터로 FAQ top1 검색 후 hit_count 증가 또는 신규 FAQ 생성. 요약문이 비어 있으면 스킵."""
    if not summary_text.strip():
        return
    try:
        faq_hit, faq_score = await search_faq_top1_by_vector(summary_vector)

        # 1. FAQ 매칭 결과가 없거나 유사도가 LOW_SIMILARITY_THRESHOLD 미만이면 신규 FAQ 생성
        if faq_hit is None or faq_score < LOW_SIMILARITY_THRESHOLD:
            await create_and_index_faq(
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                category=category,
            )
            
        # 2. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 이상이면 hit_count 증가
        elif faq_score >= HIGH_SIMILARITY_THRESHOLD:
            await increment_faq_hit_count(faq_hit["_id"])

        # 3. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 미만이면 LLM으로 동일 질문 여부 판별
        else:
            faq_question = (faq_hit.get("_source") or {}).get("question", "")
            if llm_same_question(summary_text, faq_question):
                await increment_faq_hit_count(faq_hit["_id"])
            else:
                await create_and_index_faq(
                    source_consultation_id=str(consultation_id),
                    summary_text=summary_text,
                    full_text=full_text,
                    category=category,
                )
    except Exception as e:
        logger.warning("FAQ 매칭/생성 중 오류 (상담 이력 인덱싱은 완료됨): %s", e)


def _build_full_text(messages: list[ConsultationMessages]) -> str:
    """메시지 리스트를 message_seq 순으로, 발화자 표시를 붙여 이어붙인 전체 텍스트."""
    SENDER_LABEL = {
        SenderType.CUSTOMER: "고객",
        SenderType.AGENT: "상담사",
        SenderType.SYSTEM: "시스템",
    }
    sorted_msgs = sorted(messages, key=lambda m: m.message_seq)
    parts = []
    for m in sorted_msgs:
        label = SENDER_LABEL.get(m.sender_type, "알 수 없음")
        parts.append(f"{label}: {m.content or ''}")
    return "\n".join(parts)


def _category_from_consultation(consultation) -> str:
    """상담에서 category 문자열 추출 (issue_type_id 등 활용 가능)."""
    if getattr(consultation, "issue_type_id", None) is not None:
        return str(consultation.issue_type_id)
    if getattr(consultation, "product_line_code", None) is not None:
        return consultation.product_line_code.value
    return "ETC"
