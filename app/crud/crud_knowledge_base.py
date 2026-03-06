from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_base import KnowledgeBase
from loguru import logger
from datetime import datetime
from sqlalchemy import update

async def insert_knowledge_base(session: AsyncSession, knowledge_base: KnowledgeBase) -> KnowledgeBase:
    """
    KB 데이터를 DB에 저장합니다.
    """
    try:
        session.add(knowledge_base)
        await session.flush()
        return knowledge_base
    except Exception as e:
        logger.error(f"KB 데이터 저장 중 오류 발생: {e}")
        raise e

async def update_knowledge_base_hit_count_and_last_hit_at(session: AsyncSession, faq_id: str):
    """
    KB hit_count를 1 증가시키고 last_hit_at을 현재 시간으로 업데이트합니다.
    """
    try:
        await session.execute(
            update(KnowledgeBase)
            .where(KnowledgeBase.faq_id == faq_id)
            .values(
                hit_count=KnowledgeBase.hit_count + 1,
                last_hit_at=datetime.now(),
                updated_at=datetime.now()
            )
        )
        await session.flush()
    except Exception as e:
        logger.error(f"KB hit_count 증가 중 오류 발생: {e}")
        raise e