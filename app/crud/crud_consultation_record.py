from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text
from app.models.consultation_records import ConsultationRecords
from app.schemas.consultation_summary_keyword import SummaryKeywordResponse
from loguru import logger

async def get_summary_text_with_keywords_by_record_id(session: AsyncSession, record_id: int) -> ConsultationRecords | None:
    """
    상담 ID로 요약 및 키워드를 비동기 조회합니다.
    """
    query = text("""
    select rec.summary_text, group_concat(k.keyword_name) as keywords
    from consultation_records rec
    left join record_keywords rk on rec.record_id = rk.record_id
    left join keywords k on rk.keyword_id = k.keyword_id
    where rec.record_id = :record_id
    group by rec.record_id;
    """)
    logger.info(f"record_id: {record_id}")
    result = await session.execute(query, {"record_id": record_id})
    logger.info(f"result: {result}")
    row = result.mappings().first()

    if not row:
        return None

    keywords = [k.strip() for k in row['keywords'].split(',')] if row['keywords'] else [] # 키워드 리스트로 변환

    return SummaryKeywordResponse(summary=row['summary_text'], keywords=keywords)
    