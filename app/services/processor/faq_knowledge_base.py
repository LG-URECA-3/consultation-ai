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
        당신은 LG유플러스의 지식 관리(KM) 전문가이자 고객 중심 상담 설계자입니다. 
        제공된 상담 기록을 분석하여, 고객이 직접 챗봇에 물어봤을 때 즉시 도움을 줄 수 있는 '지식베이스용 FAQ'를 생성하세요.

        [핵심 미션]
        이 FAQ는 RAG 시스템의 검색 대상이 됩니다. 고객의 검색 의도를 정확히 반영한 질문과, LLM이 답변 생성 시 근거로 쓰기 좋은 명확한 답변을 작성하십시오.

        [작성 지침]
        1. 질문(question): 
        - 고객이 챗봇 검색창에 실제로 입력할 법한 문장으로 작성하십시오.
        - "셋톱박스 연결 방법", "인터넷 속도가 느려요" 처럼 핵심 증상이나 목적이 포함되어야 합니다.
        - 추상적인 표현 대신 구체적인 상황을 묘사하십시오.

        2. 답변(answer): 
        - 해결 방법(Step-by-Step)이나 정책 정보를 논리적이고 명확하게 구성하십시오.
        - 고객이 직접 수행할 수 있는 '자가 조치 사항' 위주로 서술하십시오.
        - 상담사만 알 수 있는 내부 시스템 용어는 고객 용어(예: 전산 -> 고객님 정보)로 순화하십시오.
        - 답변이 중의적이지 않도록 '조건'과 '결과'를 명확히 구분하십시오.

        3. RAG 최적화: 
        - 질문과 답변에 해당 서비스의 핵심 키워드(예: 기가와이파이, 홈매니저, 위약금 등)를 자연스럽게 포함시켜 검색 유사도를 높이십시오.

        반드시 다음 JSON 형식으로 출력하십시오: {{"question": "고객 검색 의도 기반 질문", "answer": "해결 중심의 친절한 답변"}}
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


