from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.models.consultation_search_sync import ConsultationSearchSync

async def upsert_search_sync(session: AsyncSession, sync_record: ConsultationSearchSync) -> ConsultationSearchSync | None:
    """
    상담 ID로 ES와 DB 검색 동기화. Upsert.
    """
    try:
        merged = await session.merge(sync_record)
        await session.flush() 
        return merged
    except Exception as e:
        logger.error(f"Sync 레코드 저장 실패: {e}")
        raise