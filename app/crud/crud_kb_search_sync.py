from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
from loguru import logger
from app.models.kb_search_sync import KbSearchSync

async def upsert_kb_search_sync(
    session: AsyncSession, 
    sync_record: KbSearchSync
):
    """
    ES에 faq 저장 후 DB에 동기화. 
    명시적으로 넘겨준 값만 똑똑하게 부분 업데이트(Partial Upsert)합니다.
    """
    # 1. Insert 구문 생성 
    insert_data = sync_record.model_dump(exclude_unset=True)
    insert_stmt = insert(KbSearchSync).values(**insert_data)

    # 2. 업데이트 항목만 추출. PK, 생성일자 등 제외.
    update_keys = sync_record.model_dump(
        exclude_unset=True, 
        exclude={"doc_id", "kb_id", "created_at"}
    ).keys()

    # 3. 동적 업데이트 딕셔너리 만들기
    update_dict = {
        key: getattr(insert_stmt.inserted, key) for key in update_keys
    }
    
    update_dict["source_updated_at"] = datetime.now()
    update_dict["updated_at"] = datetime.now()

    upsert_stmt = insert_stmt.on_duplicate_key_update(**update_dict)

    try:
        await session.execute(upsert_stmt)
        await session.flush()
        logger.info(f"kb_search_sync Upsert 완료!")
        return sync_record
    except Exception as e:
        logger.error(f"kb_search_sync Upsert 중 에러 발생: {e}")
        raise e