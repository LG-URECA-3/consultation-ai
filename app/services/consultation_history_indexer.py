from app.core.infrastructure import es_client
from app.services import embeddings
from app.core.infrastructure import AsyncSessionLocal
from app.crud.crud_consultation import get_consultation_by_id
from app.crud.crud_consultation_message import get_messages_by_consultation_id
from app.services.data_formatter import get_full_text
from app.schemas.consultation_search_index import ConsultationSearchIndex
from app.schemas.base.base_consultations import ConsultationBase
from loguru import logger
from app.crud.crud_consultation_search_sync import upsert_search_sync
from app.models.consultation_search_sync import ConsultationSearchSync
from app.models.enums import IndexStatus
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

async def save_index(index_name: str, consultation_id: int, document: dict):
    """Elasticsearch 인덱스 저장 함수"""
    return await es_client.index(index=index_name, id=str(consultation_id), document=document)

# 인덱스 설정
async def setup_index_if_not_exists(index_name: str):
    """인덱스가 없으면 매핑 설정을 포함하여 생성"""
    if await es_client.indices.exists(index=index_name):
        return

    logger.info(f"인덱스 '{index_name}' 생성 중...")
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
    await es_client.indices.create(index=index_name, body=index_settings)
    

#1. 동일 상담 내용 중복 저장 방지

async def fetch_and_index_consultation_history(consultation_id: int):
    """상담 데이터 조회 및 인덱스 저장 함수"""
    es_response = None

    async with AsyncSessionLocal() as session:
        consultation = await get_consultation_by_id(session, consultation_id)
        if not consultation:
            logger.error(f"상담 데이터 조회 실패: consultation_id={consultation_id}")
            return

        index_name = "consultations_histories"
        

        sync_record = ConsultationSearchSync(
            consultation_id=consultation_id,
            index_alias=index_name,
            index_status=IndexStatus.PENDING,
            source_updated_at=datetime.now(timezone.utc)
        )

        try:
            messages = await get_messages_by_consultation_id(session, consultation_id) # message_seq, sender_type, content 리스트
            full_text = get_full_text(messages) # message_seq, sender_type, content 모두 연결한 텍스트

            summary_text = await embeddings.get_summary_text(full_text)
            summary_vector = await embeddings.get_embedding(summary_text)
            
            metadata = ConsultationBase.model_validate(consultation)
            
            index_model = ConsultationSearchIndex(
                consultation_id=consultation_id,
                full_text=full_text,
                summary_text=summary_text,
                summary_vector=summary_vector,
                messages=messages,
                metadata=metadata
            )
            document = index_model.model_dump(mode="json")

            await setup_index_if_not_exists(index_name) # 인덱스 생성

            # ES에 데이터 저장 시도 / 중복 저장 방지를 위해 consultation_id를 id로 설정
            es_response = await save_index(index_name, consultation_id, document)
            
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
                return es_response