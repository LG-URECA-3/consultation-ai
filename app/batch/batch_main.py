import asyncio
import httpx

from app.batch.batch_db import async_session, engine
from app.batch.consultation_tendency_repository import fetch_consultation_ids
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

        consultation_ids = await fetch_consultation_ids(session, target_date)

    logger.info(f"{len(consultation_ids)}개 상담 분석 시작")

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