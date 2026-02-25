from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.consultation_records import ConsultationRecords

async def get_record_by_consultation_id(session: AsyncSession, consultation_id: int) -> ConsultationRecords | None:
    """
    상담 ID로 요약 및 조치 내역을 비동기 조회합니다.
    """
    statement = select(ConsultationRecords).where(ConsultationRecords.consultation_id == consultation_id)
    
    result = await session.execute(statement)
    return result.scalars().first()