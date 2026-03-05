"""FAQ 인덱스(faq_knowledge_base) 검색, hit_count 갱신, 신규 FAQ 생성 서비스."""
from __future__ import annotations

from app.core.infrastructure import openai_client
from app.schemas.llm_response import FaqQuestionAnswerResponse
from app.core.infrastructure import client


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
    
    system_prompt = """
        당신은 LG유플러스의 전문 상담 분석가입니다. 제공된 상담 요약과 원문을 분석하여, 다른 고객들도 참고할 수 있는 '일반화된 FAQ'를 생성하세요.

        [지침]
        1. 질문(question): 고객의 의도를 한 문장으로 명확하게 요약하십시오. (예: "~하는 방법은 무엇인가요?")
        2. 답변(answer): - 고객의 비정형 표현을 표준 용어(예: 셋톱박스, IPTV)로 치환하십시오.
        - 해결 방법이나 안내 사항을 요점 위주로 구성하며, 문장은 정중한 구어체(~하세요, ~입니다)를 사용하십시오.
        3. 일반화: 특정 고객의 개인정보나 고유한 상황보다는, 유사한 문제를 겪는 누구나 적용 가능한 답변으로 작성하십시오.

        반드시 다음 JSON 형식으로만 출력하십시오: {{"question": "질문 한 문장", "answer": "답변 한 문단"}}
    """

    user_prompt = f"""
        상담 요약: {summary_text}
        상담 원문: {full_text[:2000] if full_text else "(없음)"}
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=FaqQuestionAnswerResponse,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}],
        max_tokens=500,
    )
    return resp


