from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.models.consultation_search_sync import ConsultationSearchSync

async def upsert_search_sync(session: AsyncSession, sync_record: ConsultationSearchSync) -> ConsultationSearchSync | None:
    """
    상담 ID로 ES와 DB 검색 동기화. Upsert.
    """
    try:
        result = await session.execute(
            select(ConsultationSearchSync).where(
                ConsultationSearchSync.consultation_id == sync_record.consultation_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.index_alias = sync_record.index_alias
            existing.es_doc_id = sync_record.es_doc_id
            existing.index_status = sync_record.index_status
            existing.source_updated_at = sync_record.source_updated_at
            existing.last_indexed_at = sync_record.last_indexed_at
            existing.last_attempt_at = sync_record.last_attempt_at
            existing.retry_count = sync_record.retry_count
            existing.last_error = sync_record.last_error
            existing.updated_at = sync_record.updated_at
            await session.flush()
            return existing
        else:
            session.add(sync_record)
            await session.flush()
            return sync_record
    except Exception as e:
        logger.error(f"Sync 레코드 저장 실패: {e}")
        raise