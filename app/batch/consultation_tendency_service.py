import json
import argparse
from sqlalchemy import text
from app.batch.consultation_tendency_repository import INSERT_SQL, fetch_customer_messages, UPSERT_PROCESSING_SQL, \
    UPDATE_SUCCESS_SQL, UPDATE_FAILED_SQL
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

async def analyze_and_save(session_factory, client, consultation_id):

    async with session_factory() as session:

        customer_id, messages = await fetch_customer_messages(session, consultation_id)

        if not messages:
            logger.info(f"{consultation_id} 메시지 없음")
            return

        try:

            # 처리 시작 (UPSERT)
            await session.execute(
                text(UPSERT_PROCESSING_SQL),
                {
                    "consultation_id": consultation_id,
                    "customer_id": customer_id
                }
            )

            await session.commit()

            # AI 분석
            analysis_result = await call_analysis_api(client, consultation_id, messages)

            # 분석 결과 저장
            await save_analysis(session, consultation_id, customer_id, analysis_result)

            # 성공 처리
            await session.execute(
                text(UPDATE_SUCCESS_SQL),
                {"consultation_id": consultation_id}
            )

            await session.commit()

            logger.info(f"{consultation_id} 분석 완료")

        except Exception as e:

            await session.execute(
                text(UPDATE_FAILED_SQL),
                {"consultation_id": consultation_id}
            )

            await session.commit()

            logger.error(f"{consultation_id} 처리 실패: {e}")

            raise
