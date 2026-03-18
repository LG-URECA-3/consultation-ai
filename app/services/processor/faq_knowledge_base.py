"""FAQ 인덱스(faq_knowledge_base) 검색, hit_count 갱신, 신규 FAQ 생성 서비스."""
from __future__ import annotations

from app.core.infrastructure import openai_client
from app.schemas.llm_response import FaqQuestionAnswerResponse
from app.core.infrastructure import client
from datetime import datetime


def llm_same_question(summary_text: str, faq_question: str) -> bool:
    """상담 요약이 FAQ 질문과 같은 질문인지 LLM으로 판별. 동일하면 True."""
    prompt = f"""다음 상담 요약이 아래 FAQ 질문과 같은 질문인지 판단해줘.

    상담 요약: {summary_text}

    FAQ 질문: {faq_question}

    동일하면 YES, 아니면 NO로만 답해줘.
    """

    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
    )
    text = (resp.choices[0].message.content or "").strip().upper()
    return "YES" in text


def _llm_generate_faq_question_answer(summary_text: str, full_text: str) -> tuple[str, str]:
    """상담 요약/원문을 바탕으로 FAQ용 질문·답변 문장 생성. (question, answer)."""
    
    # system_prompt = """
    #     당신은 LG유플러스의 전문 상담 분석가입니다. 제공된 상담 요약과 원문을 분석하여, 다른 고객들도 참고할 수 있는 '일반화된 FAQ'를 생성하세요.

    #     [지침]
    #     1. 질문(question): 고객의 의도를 한 문장으로 명확하게 요약하십시오. (예: "~하는 방법은 무엇인가요?")
    #     2. 답변(answer): - 고객의 비정형 표현을 표준 용어(예: 셋톱박스, IPTV)로 치환하십시오.
    #     - 해결 방법이나 안내 사항을 요점 위주로 구성하며, 문장은 정중한 구어체(~하세요, ~입니다)를 사용하십시오.
    #     3. 일반화: 특정 고객의 개인정보나 고유한 상황보다는, 유사한 문제를 겪는 누구나 적용 가능한 답변으로 작성하십시오.

    #     반드시 다음 JSON 형식으로만 출력하십시오: {{"question": "질문 한 문장", "answer": "답변 한 문단"}}
    # """

    system_prompt = """
    당신은 LG유플러스의 지식 관리(KM) 전문가입니다. 
    제공된 상담 기록을 분석하여 [질문]과 [답변] 딱 두 가지 필드만 사용하는 실용적인 FAQ를 생성하십시오.

    [핵심 미션]
    - 질문(question): 고객이 검색창에 칠 법한 '현상'과 '핵심 원인'을 결합하여 작성하십시오.
    - 답변(answer): 마크다운 기호 없이 오직 '줄바꿈'만 사용하여 UI에 맞게 구성하십시오.

    [작성 지침]
    1. 일반화 원칙 (Universal Principle):
    - 개인정보(지명, 이름 등)는 삭제하되, **문제의 원인(데이터 소진, 외부입력 설정 오류, 기지국 점검 등)**은 반드시 질문 문장에 포함하십시오.
    - 예: (X) "인터넷이 느려요" -> (O) "데이터 소진으로 인터넷 속도가 느려졌어요"
    - 예: (X) "화면이 안 나와요" -> (O) "TV 화면이 검게 나오고 외부입력 신호가 없습니다"
    - '고객님'과 같이 특정 대상을 언급하지 마십시오.
    - 개인 정보(지명, 이름 등), 개인의 고유한 상황(개인의 일정-날짜/시간, 개인 상황, 개인 특성 등)을 배제하고 모든 고객에게 포괄적으로 적용되는 '보편적 서비스 정보'로 재구성하십시오.
    - 만약, 현상의 원인이 기지국 공사, 장비 업데이트, 네트워크 장애, 데이터 소진 등 '서비스/기기' 측면의 문제이고, 시기(오늘/어제/이번달/지난달/작년 등)에 대한 정보가 포함되어야 한다다면 정확한 일시(예: 오늘 오후 6시 -> 2026.03.18 오후 6시)를 질문과 답변 문장에 포함하십시오.
    - 답변에 오늘, 어제, 이번달, 작년 등과 같은 시기에 대한 상대적 표현을 사용하지 마십시오.
    - 텍스트 외의 특수 기호는 최소화하십시오.
    - 키워드 필드가 따로 없으므로, 문장 안에 핵심적인 현상 단어가 포함되도록 하십시오.

    2. 질문(question): 
    - 고객이 처음 뱉는 불편한 '증상'을 증상의 '구체적 상황/원인'과 결합하여 한 문장으로 작성하십시오. 
    - 질문 문장 안에 핵심적인 다른 질문과 차별되는 핵심 키워드가 포함되도록 하십시오.(상품권, 소액결제, 셋톱박스 등)

    3. 답변(answer): 
    - 마크다운(**, #, -, > 등)은 절대 사용하지 마십시오. 오직 줄바꿈(\n)만 사용합니다.
    - 첫 번째 줄: [분류]와 핵심 주제를 한 줄로 요약하십시오. (UI 핑크 박스 노출용)
    - 두 번째 줄 이후: 줄바꿈을 활용하여 상세 내용을 설명하십시오. 단계가 필요하면 '1.' 처럼 번호만 사용하십시오.
    - 문체: 친절하고 명확한 문장(~입니다, ~하세요)으로 작성하십시오.
    - 답변 길이: 최대 350자를 넘지 않게 하십시오.

    반드시 다음 JSON 형식으로 출력하십시오:
    {{
    "question": "고객 현상 중심 질문",
    "answer": "[내용분류] 핵심 주제 요약\\n\\n상세 설명 내용..."
    }}
    """

    user_prompt = f"""
        상담 요약: {summary_text}
        상담 원문: {full_text[:2000] if full_text else "(없음)"}
        현재 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    """

    resp = client.chat.completions.create(
        model="gpt-4o",
        response_model=FaqQuestionAnswerResponse,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}],
        max_tokens=500,
    )
    return resp


