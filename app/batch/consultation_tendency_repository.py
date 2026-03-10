from sqlalchemy import text

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
SELECT c.consultation_id
FROM consultations c
LEFT JOIN consultation_tendency t
  ON c.consultation_id = t.consultation_id
WHERE DATE(c.created_at) = :target_date
AND (t.batch_status IS NULL OR t.batch_status != 'SUCCESS');
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

UPSERT_PROCESSING_SQL = """
INSERT INTO consultation_tendency
(consultation_id, customer_id, batch_status)
VALUES (:consultation_id, :customer_id, 'PROCESSING')
ON DUPLICATE KEY UPDATE
batch_status = IF(batch_status='SUCCESS','SUCCESS','PROCESSING');
"""

UPDATE_SUCCESS_SQL = """
UPDATE consultation_tendency
SET batch_status='SUCCESS'
WHERE consultation_id=:consultation_id
"""

UPDATE_FAILED_SQL = """
UPDATE consultation_tendency
SET batch_status='FAILED'
WHERE consultation_id=:consultation_id
"""

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