import json
import argparse
from sqlalchemy import text

import app.batch.consultation_tendency_repository as repo
from app.batch.tendency_api import logger, call_analysis_api


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
# DB 저장
# =========================

async def save_analysis(session, consultation_id, customer_id, analysis_result):

    vector = analysis_result.get("personality_vector")

    if not isinstance(vector, list) or len(vector) != 6:
        vector = [0, 0, 0, 0, 0, 0]

    await session.execute(
        text(repo.INSERT_ANALYSIS_SQL),
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

async def analyze_and_save(session_factory, client, consultation_id):

    async with session_factory() as session:

        customer_id, messages = await repo.fetch_customer_messages(session, consultation_id)

        if not messages:
            logger.info(f"{consultation_id} 메시지 없음")
            return

        try:

            await repo.upsert_processing(session, consultation_id, customer_id)
            await session.commit()

            analysis_result = await call_analysis_api(client, consultation_id, messages)

            await save_analysis(session, consultation_id, customer_id, analysis_result)

            await repo.update_success(session, consultation_id)

            await session.commit()

            logger.info(f"{consultation_id} 분석 완료")

        except Exception as e:

            await repo.update_failed(session, consultation_id)
            await session.commit()

            logger.error(f"{consultation_id} 처리 실패: {e}")

            raise