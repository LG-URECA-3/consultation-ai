from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert
from loguru import logger
from datetime import datetime
from app.models.consultation_search_sync import ConsultationSearchSync

async def upsert_search_sync(session: AsyncSession, sync_record: ConsultationSearchSync) -> ConsultationSearchSync:
    """
    일부 값만 세팅해서 넘기면, 해당 값만 안전하게 업데이트하는 Upsert
    """
    try:
        # 1. SQLModel 객체를 딕셔너리로 변환
        insert_data = sync_record.model_dump(exclude_unset=True)
        insert_stmt = insert(ConsultationSearchSync).values(**insert_data)

        # 2. 업데이트할 '일부 값'만 동적으로 추출. PK, 생성일자 등 제외.
        update_keys = sync_record.model_dump(
            exclude_unset=True, 
            exclude={"doc_id", "created_at"}
        ).keys()

        # 3. 동적 업데이트 딕셔너리 생성
        update_dict = {
            key: getattr(insert_stmt.inserted, key) for key in update_keys
        }
        # 수정 시간 현재 시간으로 갱신
        update_dict["updated_at"] = datetime.now()

        # 4. 동적 딕셔너리 언패킹
        upsert_stmt = insert_stmt.on_duplicate_key_update(**update_dict)

        await session.execute(upsert_stmt)
        await session.flush()
        logger.info(f"consultation_search_sync Upsert 완료!")
        return sync_record

    except Exception as e:
        logger.error(f"consultation_search_sync Upsert 중 에러 발생: {e}")
        raise