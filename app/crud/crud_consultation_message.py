from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.consultation_messages import ConsultationMessages
from app.schemas.base.base_consultation_messages import ConsultationMessageBase

async def get_messages_by_consultation_id(session: AsyncSession, consultation_id: int) -> list[ConsultationMessages]:
    """
    상담 ID에 속한 모든 메시지를 순서(message_seq)대로 비동기 조회합니다.
    """
    statement = (
        select(ConsultationMessages)
        .where(ConsultationMessages.consultation_id == consultation_id)
        .order_by(ConsultationMessages.message_seq) # 순서 보장 필수
    )
    
    result = await session.execute(statement)
    # 리스트로 변환하여 반환
    return list(result.scalars().all())