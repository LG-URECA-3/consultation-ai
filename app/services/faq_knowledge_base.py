"""FAQ 인덱스(faq_knowledge_base) 검색, hit_count 갱신, 신규 FAQ 생성 서비스."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from app.services import embeddings
from app.core.infrastructure import es_client, openai_client
from app.schemas.faq_doc import FaqDoc
from app.models.enums import ProductLineCode
from app.schemas.llm_response import FaqQuestionAnswerResponse
from app.services.es_faq import setup_faq_index_if_not_exists
from app.core.infrastructure import client
from loguru import logger

FAQ_INDEX = "faq_knowledge_base"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 512

HIGH_SIMILARITY_THRESHOLD = 0.95
LOW_SIMILARITY_THRESHOLD = 0.6

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


async def create_and_index_faq(
    source_consultation_id: str,
    summary_text: str,
    full_text: str,
    product_line_code: ProductLineCode,
) -> dict:
    """LLM으로 question/answer 생성 후 question_vector 임베딩해 faq_knowledge_base에 저장."""
    await setup_faq_index_if_not_exists()

    try:
        resp = _llm_generate_faq_question_answer(summary_text, full_text)
        question = resp.question
        answer = resp.answer
        logger.info(f"FAQ 생성 완료: {question}, {answer}")

        question_vector = await embeddings.get_embedding(question)
    except Exception as e:
        logger.error(f"FAQ 생성 중 OPENAI API 오류 발생: {e}")
        raise e

    faq_id = "faq_" + uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    doc = FaqDoc(
        faq_id=faq_id,
        source_consultation_id=source_consultation_id,
        question=question,
        answer=answer,
        question_vector=question_vector,
        product_line_code=product_line_code.value,
        hit_count=1,
        created_at=created_at,
    )
    logger.info(f"FAQ 문서 생성 완료: {faq_id}")
    try:
        document = doc.model_dump(mode="json")
        es_response = await es_client.index(index=FAQ_INDEX, id=faq_id, document=document)
        logger.success(f"FAQ 생성 완료: {dict(es_response)}")
        return dict(es_response)
    except Exception as e:
        logger.error(f"FAQ 생성 중 ES 오류 발생: {e}")
        raise e


