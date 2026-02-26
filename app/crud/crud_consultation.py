from sqlalchemy.ext.asyncio import AsyncSession
from app.models.consultations import Consultation
from app.schemas.base.base_consultations import ConsultationBase

async def get_consultation_by_id(session: AsyncSession, consultation_id: int) -> Consultation | None:
    """
    상담 ID로 기본 상담 정보 전체를 비동기 조회합니다.
    """
    return await session.get(Consultation, consultation_id)

# ES 저장에 필요한 데이터만 추출 - 현재 사용 안함.
async def get_consultation_base_by_id(session: AsyncSession, consultation_id: int) -> ConsultationBase | None:
    """
    상담 ID로 기본 상담 정보(ConsultationBase 필드)만 비동기 조회합니다.
    """
    consultation = await session.get(Consultation, consultation_id)

    if not consultation:
        return None
        
    return consultation # fastapi 자동 필터링