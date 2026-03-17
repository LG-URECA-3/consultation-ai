import json
import time
import re
import os
from google import genai
from google.genai import types

MODEL = "gemini-3-flash-preview"

INPUT_FILE = "app/generate/personas.json"
OUTPUT_FILE = "app/generate/consultations.json"

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def extract_json(text):

    match = re.search(r"\{[\s\S]*\}", text)

    if match:
        return match.group()

    return None


def call_llm(prompt):

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7
        )
    )

    if not response.text:
        return None

    return response.text


def generate_consultation(persona, topic):

    prompt = f"""
    당신은 한국 통신사 LG유플러스 고객센터 상담 시뮬레이터입니다.
    실제 콜센터 상담 매뉴얼을 기반으로 자연스러운 상담 대화를 생성하세요.

    중요 규칙

    1. 반드시 한국어만 사용
    2. 중국어, 영어 사용 금지
    3. conversation 객체에는 speaker 와 text만 사용
    4. context, note, emotion 같은 추가 필드 생성 금지
    5. JSON 외 다른 설명 출력 금지

    [고객 정보]
    이름: {persona["name"]}
    직업: {persona["job"]}
    지역: {persona["region"]}

    [상담 주제]
    {topic}

    ----------------------------------

    콜센터 상담 흐름 규칙

    1. 상담사 첫 멘트

    반드시 아래 형식으로 시작

    "안녕하세요, LG유플러스 상담사 OOO입니다. 무엇을 도와드릴까요?"

    - 상담사는 고객 이름을 먼저 말하지 않습니다
    - 고객 정보는 아직 모르는 상태입니다

    ----------------------------------

    2. 고객 문의

    고객이 상담 주제와 관련된 문의를 자연스럽게 설명합니다.

    고객은 처음부터

    - 이름
    - 직업
    - 지역

    같은 정보를 말하지 않습니다.

    ----------------------------------

    3. 고객 정보 확인

    상담사는 반드시 아래 방식으로 고객 정보를 요청합니다.

    "정확한 상담을 위해 고객님 성함과 연락처 확인 부탁드립니다."

    고객이 이름을 말합니다.

    ----------------------------------

    4. 상담 진행

    상담사는 문제 해결을 위해 추가 질문을 합니다.

    예
    - 이용 중 요금제
    - 사용 상황
    - 발생 시점

    ----------------------------------

    5. 조회 또는 확인이 필요할 때

    반드시 양해 멘트를 사용합니다.

    예시) "확인 후 안내드리겠습니다. 잠시만 기다려주시겠습니까?"

    ----------------------------------

    6. 해결 안내

    문제 원인 설명 후 해결 방법을 안내합니다.

    ----------------------------------

    7. 상담 마무리

    상담사는 반드시 아래 구조로 마무리합니다.

    "안내드린 내용으로 도움되셨을까요?"
    "다른 궁금한 점 있으시면 언제든지 연락주세요."
    "LG유플러스 상담사 OOO였습니다. 감사합니다."

    ----------------------------------

    대화 규칙

    - 총 12~16턴 생성
    - 상담사는 상대를 부를때 항상 "고객님" 사용
    - 상담사는 정중한 말투
    - 고객은 일반 사용자처럼 자연스럽게 질문
    - 실제 콜센터 통화처럼 자연스러운 흐름 유지

    ----------------------------------

    출력 JSON 구조

    {{
     "scenario": {{
       "customer_problem": "",
       "context": "",
       "agent_solution": ""
     }},
     "conversation":[
      {{
       "speaker":"agent",
       "text":""
      }},
      {{
       "speaker":"customer",
       "text":""
      }}
     ]
    }}
    """

    result = call_llm(prompt)

    json_text = extract_json(result)

    if not json_text:
        print("JSON 추출 실패")
        print(result)
        return None

    try:
        data = json.loads(json_text)

        cleaned = []

        for msg in data["conversation"]:
            cleaned.append({
                "speaker": msg.get("speaker"),
                "text": msg.get("text")
            })

        data["conversation"] = cleaned

        return data

    except:
        print("JSON 파싱 실패")
        print(result)
        return None


def load_existing_results():

    if not os.path.exists(OUTPUT_FILE):
        return []

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_results(results):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main():

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        personas = json.load(f)["personas"]

    results = load_existing_results()

    consultation_id = len(results) + 1

    print(f"기존 데이터 {len(results)}개 로드")

    for persona in personas:

        for topic in persona["topics"]:

            print(f"생성중: {persona['name']} / {topic}")

            consultation = generate_consultation(persona, topic)

            if not consultation:
                print("생성 실패")
                continue

            results.append({
                "consultation_id": consultation_id,
                "persona": persona["name"],
                "topic": topic,
                "scenario": consultation["scenario"],
                "conversation": consultation["conversation"]
            })

            consultation_id += 1

            save_results(results)

            print(f"저장 완료 (현재 {len(results)}개)")

            time.sleep(0.5)

    print("상담 데이터 생성 완료:", OUTPUT_FILE)


if __name__ == "__main__":
    main()