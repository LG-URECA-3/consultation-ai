import asyncio
import logging
import json
import re
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# -----------------------------
# ENUM 정의
# -----------------------------
VALID_ENUMS = {
    "analysis_status": ["ANALYZABLE", "NOT_ANALYZABLE"],
    "price_sensitivity": ["HIGH", "MID", "LOW"],
    "decision_style": ["CAUTIOUS", "IMPULSIVE", "INFO_SEEKING"],
    "anxiety_level": ["HIGH", "MID", "LOW"],
    "sentiment_label": ["NEGATIVE", "NEUTRAL", "POSITIVE"],
    "complaint_type": ["BILLING", "ROAMING", "DEVICE", "CANCEL", "TECH_SUPPORT", "ETC"],
}

# -----------------------------
# 프롬프트
# -----------------------------
def build_prompt(messages):
    return f"""
너는 JSON만 출력하는 API 서버다.

절대 규칙:
1. JSON 외 아무것도 출력 금지
2. 설명, 주석, 코드블록 절대 금지
3. 모든 필드 반드시 포함
4. ENUM 틀리면 전체 실패

ENUM:
analysis_status: ANALYZABLE, NOT_ANALYZABLE
price_sensitivity: HIGH, MID, LOW
decision_style: CAUTIOUS, IMPULSIVE, INFO_SEEKING
anxiety_level: HIGH, MID, LOW
sentiment_label: NEGATIVE, NEUTRAL, POSITIVE
complaint_type: BILLING, ROAMING, DEVICE, CANCEL, TECH_SUPPORT, ETC

personality_vector 의미:
[0] 가격 민감도
[1] 정보 탐색 성향
[2] 감정 민감도
[3] 충동성
[4] 불안도
[5] 논리성
(모든 값은 0~1)

출력 형식:
{{
  "analysis_status": "",
  "price_sensitivity": "",
  "decision_style": "",
  "anxiety_level": "",
  "sentiment_label": "",
  "sentiment_score": 0,
  "core_need": "",
  "complaint_type": "",
  "consultation_summary": "",
  "recommended_strategy": "",
  "personality_vector": [0,0,0,0,0,0]
}}

출력 예시:
{{
  "analysis_status": "ANALYZABLE",
  "price_sensitivity": "HIGH",
  "decision_style": "CAUTIOUS",
  "anxiety_level": "MID",
  "sentiment_label": "NEGATIVE",
  "sentiment_score": -0.4,
  "core_need": "요금 부담 완화",
  "complaint_type": "BILLING",
  "consultation_summary": "요금 과다 청구로 인한 불만",
  "recommended_strategy": "요금제 변경 및 할인 안내",
  "personality_vector": [0.8, 0.2, 0.6, 0.3, 0.5, 0.4]
}}

대화:
{chr(10).join(messages)}
"""

# -----------------------------
# JSON 추출
# -----------------------------
def extract_json(text: str):
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else None

# -----------------------------
# 검증
# -----------------------------
def validate_result(data):

    for key, allowed in VALID_ENUMS.items():
        if data.get(key) not in allowed:
            logger.warning(f"{key} 값 오류: {data.get(key)}")
            return False

    vec = data.get("personality_vector")

    if not isinstance(vec, list) or len(vec) != 6:
        logger.warning("personality_vector 형식 오류")
        return False

    for v in vec:
        if not isinstance(v, (int, float)) or not (0 <= v <= 1):
            logger.warning("personality_vector 값 범위 오류")
            return False

    score = data.get("sentiment_score")
    if not isinstance(score, (int, float)) or not (-1 <= score <= 1):
        logger.warning("sentiment_score 범위 오류")
        return False

    return True

# -----------------------------
# Gemini 호출
# -----------------------------
async def call_analysis_api(client_unused, consultation_id, messages):

    prompt = build_prompt(messages)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    top_p=0.8
                )
            )

            raw = response.text

            cleaned = extract_json(raw)

            if not cleaned:
                raise Exception("JSON 추출 실패")

            data = json.loads(cleaned)

            if validate_result(data):
                return data

            logger.warning(f"{consultation_id} 검증 실패 → 재시도")

        except Exception as e:
            logger.warning(f"{consultation_id} Gemini 오류: {e}")

        await asyncio.sleep(1)

    raise Exception(f"{consultation_id} 3회 실패")