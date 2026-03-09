"""상담 이력을 DB에서 조회해 consultation_histories 인덱스에 저장하는 서비스."""
from __future__ import annotations

from app.core.infrastructure import es_client
from app.services import embeddings
from app.core.infrastructure import AsyncSessionLocal

from app.core.infrastructure import es_client
from app.models.consultation_messages import ConsultationMessages
from app.models.enums import SenderType
from app.crud.crud_consultation import get_consultation_by_id
from app.crud.crud_consultation_message import get_messages_by_consultation_id
from app.schemas.consultation_history_doc import ConsultationHistoryDoc
from app.schemas.base.base_consultations import ConsultationBase
from loguru import logger
from app.crud.crud_consultation_search_sync import upsert_search_sync
from app.models.consultation_search_sync import ConsultationSearchSync
from app.models.enums import IndexStatus
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from app.crud.crud_consultation_record import get_record_by_consultation_id
from app.schemas.consultation_history_es import (
    CustomerPersona,
)
from app.services.es_consultation import setup_index_if_not_exists
from app.services.es_consultation import (
    _get_consultation_doc_from_es,
    save_index,
    CONSULTATION_HISTORIES_INDEX
)

    
async def fetch_and_index_consultation_history(consultation_id: int) -> ConsultationHistoryDoc | None:
    """
    Step 1: ES 또는 DB에서 상담 데이터를 확보한 뒤 가공·ES 인덱싱하여 ConsultationHistoryDoc 반환.
    ES에 문서가 있으면 인덱싱 없이 doc만 반환. 없으면 DB 조회 후 doc 생성·인덱싱 후 반환.
    """
    # ES 저장된 상담 내역이 있는지 조회
    try:
        await setup_index_if_not_exists() # 인덱스 생성

        # 동일 id로 생성된 문서가 있는지 조회
        doc = await _get_consultation_doc_from_es(consultation_id)
        if doc and doc is not None: # 있으면 리턴(중복저장 방지)
            logger.info(f"ES consultation_histories에 문서가 있습니다. 문서를 조회합니다.: {doc.consultation_id}")
            return doc
    except Exception as e: # None 반환으로 수정 고려.
        logger.debug(f"ES consultation_histories에 문서가 없습니다: {e}")

    # 동일 id로 생성된 문서가 없으면 DB에서 상담 데이터를 조회 - 저장 흐름
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
 
# 이거 필요없으면 지워도 되나요?
def _category_from_consultation(consultation) -> str:
    """상담에서 category 문자열 추출 (issue_type_id 등 활용 가능)."""
    if getattr(consultation, "issue_type_id", None) is not None:
        return str(consultation.issue_type_id)
    if getattr(consultation, "product_line_code", None) is not None:
        return consultation.product_line_code.value
    return "ETC"
