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


def is_valid_result(data):
    required_keys = [
        "analysis_status",
        "price_sensitivity",
        "decision_style",
        "anxiety_level",
        "sentiment_label",
        "sentiment_score",
        "complaint_type",
        "consultation_summary",
        "recommended_strategy",
        "personality_vector"
    ]

    for key in required_keys:
        if key not in data:
            return False

    return True


def log_failed_result(consultation_id, error_msg):
    with open("failed_results.json", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "consultation_id": consultation_id,
            "error": str(error_msg)
        }, ensure_ascii=False) + "\n")


# =========================
# DB 저장
# =========================

async def save_analysis(session, consultation_id, customer_id, analysis_result):

    vector = analysis_result.get("personality_vector")

    # ❗ 잘못된 데이터는 저장하지 않음
    if not isinstance(vector, list) or len(vector) != 6:
        raise ValueError("invalid personality_vector")

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
            "sentiment_score": analysis_result.get("sentiment_score") or 0,
            "core_need": analysis_result.get("core_need") or "",
            "complaint_type": normalize_enum(analysis_result.get("complaint_type")),
            "consultation_summary": analysis_result.get("consultation_summary") or "",
            "recommended_strategy": analysis_result.get("recommended_strategy") or "",
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
            logger.info(f"[{consultation_id}] 메시지 없음")
            return

        try:
            # 처리중 상태 저장
            await repo.upsert_processing(session, consultation_id, customer_id)
            await session.commit()

            # ✅ API 내부에서 재시도 수행됨
            analysis_result = await call_analysis_api(client, consultation_id, messages)

            # ✅ 결과 검증
            if not is_valid_result(analysis_result):
                raise ValueError("invalid analysis result")

            # DB 저장
            await save_analysis(session, consultation_id, customer_id, analysis_result)

            # 성공 처리
            await repo.update_success(session, consultation_id)
            await session.commit()

            logger.info(f"[{consultation_id}] 분석 완료")

        except Exception as e:

            # 실패 로그 저장
            log_failed_result(consultation_id, e)

            # 실패 상태 업데이트
            await repo.update_failed(session, consultation_id)
            await session.commit()

            logger.error(f"[{consultation_id}] 처리 실패: {e}")

            # 필요하면 상위로 던짐
            raise