from sqlalchemy.ext.asyncio import AsyncSession
from app.models.consultations import Consultation

async def get_consultation_by_id(session: AsyncSession, consultation_id: int) -> Consultation | None:
    """
    상담 ID로 기본 상담 메타데이터 정보를 비동기 조회합니다.
    """
    return await session.get(Consultation, consultation_id)