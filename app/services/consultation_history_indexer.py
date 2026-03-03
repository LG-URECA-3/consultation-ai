"""상담 이력을 DB에서 조회해 consultation_histories 인덱스에 저장하는 서비스."""
from __future__ import annotations

from app.core.infrastructure import es_client
from app.services import embeddings
from app.core.infrastructure import AsyncSessionLocal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.infrastructure import es_client, openai_client
from app.models.consultation_messages import ConsultationMessages
from app.models.enums import SenderType
from app.crud.crud_consultation import get_consultation_by_id
from app.crud.crud_consultation_message import get_messages_by_consultation_id
from app.services.data_formatter import get_full_text
from app.schemas.consultation_search_index import ConsultationHistoryDoc
from app.schemas.base.base_consultations import ConsultationBase
from loguru import logger
from app.crud.crud_consultation_search_sync import upsert_search_sync
from app.models.consultation_search_sync import ConsultationSearchSync
from app.models.enums import IndexStatus
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from app.crud.crud_consultation_record import get_record_by_consultation_id
from app.schemas.consultation_history_es import (
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



CONSULTATION_HISTORIES_INDEX = "consultations_histories"

async def save_index(consultation_id: int, document: dict):
    """Elasticsearch 인덱스 저장 함수"""
    return await es_client.index(index=CONSULTATION_HISTORIES_INDEX, id=str(consultation_id), document=document)

# 인덱스 설정
async def setup_index_if_not_exists():
    """인덱스가 없으면 매핑 설정을 포함하여 생성"""
    if await es_client.indices.exists(index=CONSULTATION_HISTORIES_INDEX):
        return

    logger.info(f"인덱스 '{CONSULTATION_HISTORIES_INDEX}' 생성 중...")
    index_settings = { # 성능 테스트 후 필요시 nori_tokenizer 도입
        "settings": {
        "index": {
            "refresh_interval": "1s"
            }
        },
        "mappings": {
            "properties": {
                "consultation_id": {"type": "long"},
                "full_text": {"type": "text"},
                "summary_text": {"type": "text"},
                "summary_vector": {"type": "dense_vector", "dims": 512, "index": True, "similarity": "cosine"},
                "keywords": {"type": "keyword"},

                "messages": {"type": "nested",
                    "properties": {
                        "message_seq": {"type": "integer"},
                        "sender_type": {"type": "keyword"},
                        "content": {"type": "text"}
                    }
                },
                "metadata": {"type": "object", "properties": {
                    "customer_id": {"type": "long"},
                    "agent_id": {"type": "long"},
                    "channel_code": {"type": "keyword"},
                    "product_line_code": {"type": "keyword"},
                    "final_result_code": {"type": "keyword"},
                    "started_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time"},
                    "ended_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time"},
                }}
            }
        }
    }
    await es_client.indices.create(index=CONSULTATION_HISTORIES_INDEX, body=index_settings)
    
async def fetch_and_index_consultation_history(consultation_id: int) -> ConsultationHistoryDoc | None:
    """
    Step 1: ES 또는 DB에서 상담 데이터를 확보한 뒤 가공·ES 인덱싱하여 ConsultationHistoryDoc 반환.
    ES에 문서가 있으면 인덱싱 없이 doc만 반환. 없으면 DB 조회 후 doc 생성·인덱싱 후 반환.
    """
    # ES 저장된 상담 내역이 있는지 조회
    try:
        await setup_index_if_not_exists() # 인덱스 생성

        doc = await _get_consultation_doc_from_es(consultation_id)
        if doc and doc is not None: # 있으면 리턴(중복저장 방지)
            return doc
    except Exception as e:
        logger.debug("ES consultation_histories에 문서가 없습니다: %s", e)


    async with AsyncSessionLocal() as session:
        consultation = await get_consultation_by_id(session, consultation_id)
        if not consultation:
            logger.error(f"상담 데이터 조회 실패: consultation_id={consultation_id}")
            return None

        sync_record = ConsultationSearchSync(
            consultation_id=consultation_id,
            index_alias=CONSULTATION_HISTORIES_INDEX,
            index_status=IndexStatus.PENDING,
            source_updated_at=datetime.now(timezone.utc)
        )

        try:
            messages = await get_messages_by_consultation_id(session, consultation_id) # message_seq, sender_type, content 리스트
            record = await get_record_by_consultation_id(session, consultation_id) # summary_text
            full_text = _build_full_text(messages) # message_seq, sender_type, content 모두 연결한 텍스트

            summary_response = await embeddings.get_summary_text(full_text)
            # summary_text = await embeddings.get_summary_text(full_text)
#             summary_text = (record.summary_text if record else "") or ""
            # if summary_text:
            if summary_response:
                summary_vector = await embeddings.get_embedding(summary_response.summary)

            customer_persona = CustomerPersona(sentiment="NEUTRAL", traits=[])
            metadata = ConsultationBase.model_validate(consultation)

            doc = ConsultationHistoryDoc(
                consultation_id=consultation_id,
                full_text=full_text,
                summary_text=summary_response.summary,
                summary_vector=summary_vector,
                messages=messages,
                keywords=summary_response.keywords,
                customer_persona=customer_persona, # 이걸 여기에 넣는게 맞는지 고민돼요
                metadata=metadata
            )
            document = doc.model_dump(mode="json")

            # ES에 데이터 저장 시도 / 중복 저장 방지를 위해 consultation_id를 id로 설정
            es_response = await save_index(consultation_id, document)

            # 응답값 출력해서 형태 확인
            logger.success(f"Elasticsearch 저장 성공! 응답 결과: {dict(es_response)}")

            #성공시
            sync_record.es_doc_id = es_response["_id"]
            sync_record.index_status = IndexStatus.INDEXED
            sync_record.last_indexed_at = datetime.now(timezone.utc)


        except Exception as e:
            # 실패 시 상태와 에러 메시지 기록
            sync_record.index_status = IndexStatus.FAILED
            sync_record.last_error = str(e)
            logger.error(f"인덱스 처리 중 작업 실패: {str(e)}")

        finally:
            sync_record.updated_at = datetime.now(timezone.utc)
            sync_record.last_attempt_at = datetime.now(timezone.utc)
            sync_record.retry_count += 1

            try:
                await upsert_search_sync(session, sync_record)
                await session.commit()
                logger.info(f"상담 인덱스 저장 완료: consultation_id={consultation_id}")

            except SQLAlchemyError as se:
                await session.rollback()
                logger.error(f"sync DB 저장 실패: {str(se)}")

            finally:
                return doc

def _build_full_text(messages: list[ConsultationMessages]) -> str:
    """메시지 리스트를 message_seq 순으로, 발화자 표시(한글 라벨)를 붙여 이어붙인 전체 텍스트."""
    SENDER_LABEL = {
        SenderType.CUSTOMER: "고객",
        SenderType.AGENT: "상담사",
        SenderType.SYSTEM: "시스템",
    }
    sorted_messages = sorted(messages, key=lambda m: m.message_seq)

    return "\n".join(
        f"{SENDER_LABEL.get(m.sender_type, '알 수 없음')}: {m.content or ''}"
        for m in sorted_messages
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

async def run_faq_from_consultation_doc(doc: ConsultationHistoryDoc) -> None:
    """
    Step 2: ConsultationHistoryDoc 기준으로 FAQ top1 매칭 후 hit_count 증가 또는 신규 FAQ 생성.
    """
    consultation_id = int(doc.consultation_id) if doc.consultation_id else 0
    await _run_faq_logic(
        consultation_id=consultation_id,
        summary_text=doc.summary_text,
        summary_vector=doc.summary_vector,
        full_text=doc.full_text,
        product_line_code=doc.metadata.product_line_code,
    )

async def _run_faq_logic(
    consultation_id: int,
    summary_text: str,
    summary_vector: list[float],
    full_text: str,
    product_line_code: str,
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
                product_line_code=product_line_code,
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
                    product_line_code=product_line_code,
                )
    except Exception as e:
        logger.warning("FAQ 매칭/생성 중 오류 (상담 이력 인덱싱은 완료됨): %s", e)

# 이거 필요없으면 지워도 되나요?
def _category_from_consultation(consultation) -> str:
    """상담에서 category 문자열 추출 (issue_type_id 등 활용 가능)."""
    if getattr(consultation, "issue_type_id", None) is not None:
        return str(consultation.issue_type_id)
    if getattr(consultation, "product_line_code", None) is not None:
        return consultation.product_line_code.value
    return "ETC"
