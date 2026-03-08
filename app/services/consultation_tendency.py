import os
import logging
import json
import httpx
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]

DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 분석 대상 상담 ID
consultation_id = 5

# FastAPI 서버 주소
ANALYZE_API_URL = "https://laurena-nonorthodox-camren.ngrok-free.dev/analyze"


# =========================
# 1️⃣ 고객 메시지 + customer_id 조회
# =========================
FETCH_SQL = """
SELECT c.customer_id, cm.content
FROM consultations c
JOIN consultation_messages cm
  ON c.consultation_id = cm.consultation_id
WHERE c.consultation_id = :consultation_id
  AND cm.sender_type = 'CUSTOMER'
ORDER BY cm.message_seq;
"""


# =========================
# 2️⃣ 분석 결과 저장 SQL
# =========================
FETCH_CONSULTATION_IDS_SQL = """
SELECT consultation_id
FROM consultations
WHERE DATE(created_at) = :target_date;
"""
INSERT_SQL = """
INSERT INTO consultation_tendency (
    consultation_id,
    customer_id,
    analysis_status,
    price_sensitivity,
    decision_style,
    anxiety_level,
    sentiment_label,
    sentiment_score,
    core_need,
    complaint_type,
    consultation_summary,
    recommended_strategy,
    personality_vector
)
VALUES (
    :consultation_id,
    :customer_id,
    :analysis_status,
    :price_sensitivity,
    :decision_style,
    :anxiety_level,
    :sentiment_label,
    :sentiment_score,
    :core_need,
    :complaint_type,
    :consultation_summary,
    :recommended_strategy,
    :personality_vector
)
ON DUPLICATE KEY UPDATE
    analysis_status = VALUES(analysis_status),
    price_sensitivity = VALUES(price_sensitivity),
    decision_style = VALUES(decision_style),
    anxiety_level = VALUES(anxiety_level),
    sentiment_label = VALUES(sentiment_label),
    sentiment_score = VALUES(sentiment_score),
    core_need = VALUES(core_need),
    complaint_type = VALUES(complaint_type),
    consultation_summary = VALUES(consultation_summary),
    recommended_strategy = VALUES(recommended_strategy),
    personality_vector = VALUES(personality_vector);
"""

def normalize_enum(value):
    if not value:
        return None
    return value.strip().upper()

async def analyze_and_save(session, consultation_id):

        result = await session.execute(
            text(FETCH_SQL),
            {"consultation_id": consultation_id}
        )

        rows = result.fetchall()

        if not rows:
            logger.info(f"{consultation_id} 메시지 없음")
            return

        customer_id = rows[0][0]
        customer_messages = [row[1] for row in rows]

        payload = {
            "consultation_id": consultation_id,
            "customer_messages": customer_messages
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(ANALYZE_API_URL, json=payload)

        if response.status_code != 200:
            logger.error(f"{consultation_id} API 실패")
            return

        analysis_result = response.json()

        vector = analysis_result.get("personality_vector")
        if not isinstance(vector, list) or len(vector) != 6:
            vector = [0, 0, 0, 0, 0, 0]

        await session.execute(
            text(INSERT_SQL),
            {
                "consultation_id": consultation_id,
                "customer_id": customer_id,
                "analysis_status": normalize_enum(analysis_result.get("analysis_status")),
                "price_sensitivity": normalize_enum(analysis_result.get("price_sensitivity")),
                "decision_style": normalize_enum(analysis_result.get("decision_style")),
                "anxiety_level": normalize_enum(analysis_result.get("anxiety_level")),
                "sentiment_label": normalize_enum(analysis_result.get("sentiment_label")),
                "sentiment_score": analysis_result.get("sentiment_score"),
                "core_need": analysis_result.get("core_need"),
                "complaint_type": normalize_enum(analysis_result.get("complaint_type")),
                "consultation_summary": analysis_result.get("consultation_summary"),
                "recommended_strategy": analysis_result.get("recommended_strategy"),
                "personality_vector": json.dumps(vector),
            }
        )

        await session.commit()

        logger.info("DB 저장 완료")

async def main():

    target_date = "2026-03-05"

    async with async_session() as session:

        result = await session.execute(
            text(FETCH_CONSULTATION_IDS_SQL),
            {"target_date": target_date}
        )

        consultation_ids = [row[0] for row in result.fetchall()]

        logger.info(f"{len(consultation_ids)}개 상담 분석 시작")

        for consultation_id in consultation_ids:
            try:
                await analyze_and_save(session, consultation_id)
            except Exception as e:
                logger.error(f"{consultation_id} 처리 실패 {e}")

        await session.commit()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())