import logging
import json
import argparse
import asyncio

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Windows asyncio 정책
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# =========================
# DB
# =========================

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


# =========================
# Logger
# =========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# API
# =========================

ANALYZE_API_URL = "https://laurena-nonorthodox-camren.ngrok-free.dev/analyze"


# =========================
# SQL
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


# =========================
# util
# =========================

def normalize_enum(value):
    if not value:
        return None
    return value.strip().upper()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        required=True,
        help="Target date (YYYY-MM-DD)"
    )
    return parser.parse_args()


# =========================
# DB 조회
# =========================

async def fetch_consultation_ids(session, target_date):

    result = await session.execute(
        text(FETCH_CONSULTATION_IDS_SQL),
        {"target_date": target_date}
    )

    return [row[0] for row in result.fetchall()]


async def fetch_customer_messages(session, consultation_id):

    result = await session.execute(
        text(FETCH_SQL),
        {"consultation_id": consultation_id}
    )

    rows = result.fetchall()

    if not rows:
        return None, []

    customer_id = rows[0][0]
    messages = [row[1] for row in rows]

    return customer_id, messages


# =========================
# API 호출
# =========================

async def call_analysis_api(client, consultation_id, messages):

    payload = {
        "consultation_id": consultation_id,
        "customer_messages": messages
    }

    response = await client.post(ANALYZE_API_URL, json=payload)

    if response.status_code != 200:
        raise Exception(f"API 실패 {consultation_id}")

    return response.json()


# =========================
# DB 저장
# =========================

async def save_analysis(session, consultation_id, customer_id, analysis_result):

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


# =========================
# 핵심 처리
# =========================

async def analyze_and_save(session, client, consultation_id):

    customer_id, messages = await fetch_customer_messages(session, consultation_id)

    if not messages:
        logger.info(f"{consultation_id} 메시지 없음")
        return

    analysis_result = await call_analysis_api(client, consultation_id, messages)

    await save_analysis(session, consultation_id, customer_id, analysis_result)

    logger.info(f"{consultation_id} 분석 완료")


# =========================
# main
# =========================

async def main():

    args = parse_args()
    target_date = args.date

    async with async_session() as session:

        consultation_ids = await fetch_consultation_ids(session, target_date)

        logger.info(f"{len(consultation_ids)}개 상담 분석 시작")

        async with httpx.AsyncClient(timeout=None) as client:

            for consultation_id in consultation_ids:
                try:
                    await analyze_and_save(session, client, consultation_id)
                except Exception as e:
                    logger.error(f"{consultation_id} 처리 실패: {e}")

        await session.commit()

    await engine.dispose()


# =========================
# run
# =========================

if __name__ == "__main__":
    asyncio.run(main())