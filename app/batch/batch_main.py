import asyncio
import httpx

from app.batch.batch_db import async_session, engine
from app.batch.consultation_tendency_repository import fetch_consultation_ids, fetch_batch_stats
from app.batch.consultation_tendency_service import analyze_and_save, parse_args
from app.batch.tendency_api import logger

# Windows asyncio 정책
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# =========================
# main
# =========================

async def main():
    print("batch start")

    args = parse_args()
    target_date = args.date


    async with async_session() as session:

        stats = await fetch_batch_stats(session, target_date)

        logger.info(f"전체 상담: {stats['total']}")
        logger.info(f"이미 분석 완료: {stats['success']}")
        logger.info(f"이전 실패: {stats['failed']}")
        logger.info(f"처리 중 상태: {stats['processing']}")
        logger.info(f"신규 상담: {stats['new']}")

        consultation_ids = await fetch_consultation_ids(session, target_date)

    async with httpx.AsyncClient(timeout=None) as client:

        for consultation_id in consultation_ids:

            try:
                await analyze_and_save(async_session, client, consultation_id)

            except Exception as e:
                logger.error(f"{consultation_id} 처리 실패: {e}")

    await engine.dispose()


# =========================
# run
# =========================

if __name__ == "__main__":
    asyncio.run(main())