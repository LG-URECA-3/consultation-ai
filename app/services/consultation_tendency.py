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
consultation_id = 1

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

async def analyze_and_save():

    async with async_session() as session:

        # 1️⃣ 데이터 조회
        result = await session.execute(
            text(FETCH_SQL),
            {"consultation_id": consultation_id}
        )

        rows = result.fetchall()

        if not rows:
            logger.info("고객 메시지 없음")
            return

        customer_id = rows[0][0]
        customer_messages = [row[1] for row in rows]

        payload = {
            "consultation_id": consultation_id,
            "customer_messages": customer_messages
        }

        # 2️⃣ FastAPI 분석 호출
        async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0)
        ) as client:
            response = await client.post(ANALYZE_API_URL, json=payload)

        if response.status_code != 200:
            logger.error(f"API 호출 실패: {response.text}")
            return

        analysis_result = response.json()

        logger.info("분석 완료")

        # 3️⃣ DB 저장
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
                "raw_response": analysis_result.get("raw_response")
            }
        )

        await session.commit()

        logger.info("DB 저장 완료")

async def main():
    try:
        await analyze_and_save()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())