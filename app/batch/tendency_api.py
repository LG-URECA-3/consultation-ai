import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

# =========================
# API
# =========================

ANALYZE_API_URL = "https://laurena-nonorthodox-camren.ngrok-free.dev/analyze"

async def call_analysis_api(client, consultation_id, messages):

    payload = {
        "consultation_id": consultation_id,
        "customer_messages": messages
    }

    for attempt in range(3):

        try:
            response = await client.post(ANALYZE_API_URL, json=payload)

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"{consultation_id} API 오류 {e}")

        await asyncio.sleep(2)

    raise Exception(f"API 3회 실패 {consultation_id}")