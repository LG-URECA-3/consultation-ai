from app.core.infrastructure import es_client
from loguru import logger
from app.schemas.consultation_history_doc import ConsultationHistoryDoc
from app.core.config import settings

CONSULTATION_HISTORIES_INDEX = "consultations_histories"

async def save_index(consultation_id: int, document: dict):
    """Elasticsearch의 consultations_histories 인덱스 저장 함수. consultation_id를 id로 설정하여 중복 저장 방지."""
    return await es_client.index(index=CONSULTATION_HISTORIES_INDEX, id=str(consultation_id), document=document)

# 인덱스 설정
async def setup_index_if_not_exists():
    """인덱스 존재 여부 확인.consultations_histories 인덱스가 없으면 매핑 설정을 포함하여 생성."""
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
                "summary_vector": {"type": "dense_vector", "dims": settings.EMBEDDING_DIMS, "index": True, "similarity": "cosine"},
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
    logger.info(f"인덱스 '{CONSULTATION_HISTORIES_INDEX}' 생성 완료")

async def _get_consultation_doc_from_es(consultation_id: int) -> ConsultationHistoryDoc | None:
    """ES consultation_histories에서 consultation_id 문서를 조회해 ConsultationHistoryDoc으로 반환."""
    try:
        resp = await es_client.get(
            index=CONSULTATION_HISTORIES_INDEX,
            id=str(consultation_id),
        )
    except Exception as e:
        logger.error("ES에서 문서를 가져오지 못했습니다. ID: %s, 사유: %s", consultation_id, e)
        return None

    src = resp.get("_source")
    if not src:
        return None
    
    return ConsultationHistoryDoc.model_validate(src)