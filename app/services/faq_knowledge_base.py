"""FAQ 인덱스(faq_knowledge_base) 검색, hit_count 갱신, 신규 FAQ 생성 서비스."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from app.core.infrastructure import es_client, openai_client
from app.schemas.faq_es import FaqDoc

FAQ_INDEX = "faq_knowledge_base"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

HIGH_SIMILARITY_THRESHOLD = 0.9
LOW_SIMILARITY_THRESHOLD = 0.6


async def ensure_faq_index() -> None:
    """faq_knowledge_base 인덱스가 없으면 question_vector 매핑으로 생성."""
    if await es_client.indices.exists(index=FAQ_INDEX):
        return
    await es_client.indices.create(
        index=FAQ_INDEX,
        mappings={
            "properties": {
                "faq_id": {"type": "keyword"},
                "source_consultation_id": {"type": "keyword"},
                "question": {"type": "text"},
                "answer": {"type": "text"},
                "question_vector": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine",
                },
                "category": {"type": "keyword"},
                "hit_count": {"type": "integer"},
                "created_at": {"type": "date"},
            }
        },
    )


async def search_faq_top1_by_vector(
    query_vector: list[float],
    num_candidates: int = 50,
) -> tuple[dict | None, float]:
    """
    query_vector로 faq_knowledge_base kNN 검색, top1 반환.
    Returns (hit, score) where hit has _id and _source, or (None, 0.0) if no hits.
    """
    if not await es_client.indices.exists(index=FAQ_INDEX):
        return None, 0.0

    resp = await es_client.search(
        index=FAQ_INDEX,
        knn={
            "field": "question_vector",
            "query_vector": query_vector,
            "k": 1,
            "num_candidates": num_candidates,
        },
        source=True,
        size=1,
    )

    hits = resp.get("hits", {}).get("hits", [])
    if not hits:
        return None, 0.0

    hit = hits[0]
    return hit, float(hit.get("_score", 0.0))


async def increment_faq_hit_count(faq_id: str) -> None:
    """기존 FAQ 문서의 hit_count를 1 증가 (ES update script)."""
    await es_client.update(
        index=FAQ_INDEX,
        id=faq_id,
        script={"source": "ctx._source.hit_count += 1", "lang": "painless"},
    )


def llm_same_question(summary_text: str, faq_question: str) -> bool:
    """상담 요약이 FAQ 질문과 같은 질문인지 LLM으로 판별. 동일하면 True."""
    prompt = f"""다음 상담 요약이 아래 FAQ 질문과 같은 질문인지 판단해줘.

상담 요약: {summary_text}

FAQ 질문: {faq_question}

동일하면 YES, 아니면 NO로만 답해줘."""

    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
    )
    text = (resp.choices[0].message.content or "").strip().upper()
    return "YES" in text


def _llm_generate_faq_question_answer(summary_text: str, full_text: str) -> tuple[str, str]:
    """상담 요약/원문을 바탕으로 FAQ용 질문·답변 문장 생성. (question, answer)."""
    
    prompt = f"""당신은 LG유플러스의 전문 상담 분석가입니다. 제공된 상담 요약과 원문을 분석하여, 다른 고객들도 참고할 수 있는 '일반화된 FAQ'를 생성하세요.

    [지침]
    1. 질문(question): 고객의 의도를 한 문장으로 명확하게 요약하십시오. (예: "~하는 방법은 무엇인가요?")
    2. 답변(answer): - 고객의 비정형 표현을 표준 용어(예: 셋톱박스, IPTV)로 치환하십시오.
    - 해결 방법이나 안내 사항을 요점 위주로 구성하며, 문장은 정중한 구어체(~하세요, ~입니다)를 사용하십시오.
    3. 일반화: 특정 고객의 개인정보나 고유한 상황보다는, 유사한 문제를 겪는 누구나 적용 가능한 답변으로 작성하십시오.

    상담 요약: {summary_text}
    상담 원문: {full_text[:2000] if full_text else "(없음)"}

    반드시 다음 JSON 형식으로만 출력하십시오: {{"question": "질문 한 문장", "answer": "답변 한 문단"}}"""

    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    text = (resp.choices[0].message.content or "").strip()

    # JSON 블록 추출
    match = re.search(r"\{[^{}]*\"question\"[^{}]*\"answer\"[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            q = data.get("question", "").strip()
            a = data.get("answer", "").strip()
            if q and a:
                return q, a
        except json.JSONDecodeError:
            pass

    # 폴백
    q = (summary_text[:200] + "…") if len(summary_text) > 200 else summary_text
    return q or "질문", summary_text or "답변"


async def create_and_index_faq(
    source_consultation_id: str,
    summary_text: str,
    full_text: str,
    category: str,
) -> FaqDoc:
    """LLM으로 question/answer 생성 후 question_vector 임베딩해 faq_knowledge_base에 저장."""
    await ensure_faq_index()

    question, answer = _llm_generate_faq_question_answer(summary_text, full_text)

    embed_res = openai_client.embeddings.create(
        input=question,
        model=EMBEDDING_MODEL,
    )
    question_vector = embed_res.data[0].embedding

    faq_id = "faq_" + uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    doc = FaqDoc(
        faq_id=faq_id,
        source_consultation_id=source_consultation_id,
        question=question,
        answer=answer,
        question_vector=question_vector,
        category=category,
        hit_count=1,
        created_at=created_at,
    )

    body = doc.to_es_body()
    await es_client.index(index=FAQ_INDEX, id=faq_id, document=body)
    return doc
