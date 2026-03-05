
#1. 특정 텍스트(요약)으로 es 검색
#2. 키워드+벡터 검색(하이브리드) -> 유사도 판단
#   => faq에 넣은 요약 임베딩과 비교. + 요약문/질문/답변으로 키워드 검색?
#   => 저장된 요약 임베딩-입력된 요약 임베딩 비교. 
#   => 요약문/질문/답변-추출된 키워드 비교.
#3. 유사도가 0.9>= 일 경우 동일 faq가 존재하는 것으로 판단
#   => 해당 faq의 faq_id 반환.. 해당 faq가 뭔지 어떻게 알지? => faq에 요약 텍스트 혹은 요약 임베딩을 저장해두자.
#4. 유사도가 0.9< 일 경우 새로운 faq로 판단
#   => 새로운 faq 저장 후 faq_id 반환
#5. 생성된 faq를 기존 faq의 질문과 한 번 더 유사도 비교. 검증.
#6. 검증 후 저장.(ES 인덱스)

from loguru import logger
from app.services.faq_knowledge_base import (
    HIGH_SIMILARITY_THRESHOLD,
    LOW_SIMILARITY_THRESHOLD,
    create_and_index_faq,
    llm_same_question,
)
from app.services.es_faq import faq_similarity_search, increment_faq_hit_count
from app.schemas.consultation_history_doc import ConsultationHistoryDoc


async def run_faq_from_consultation_doc(doc: ConsultationHistoryDoc) -> None:
    """
    Step 2: ConsultationHistoryDoc 기준으로 FAQ top1 매칭 후 hit_count 증가 또는 신규 FAQ 생성.
    """
    logger.info(f"FAQ 매칭 시작: {doc}")
    await _run_faq_logic(
        consultation_id=doc.consultation_id,
        summary_text=doc.summary_text,
        summary_vector=doc.summary_vector,
        full_text=doc.full_text,
        product_line_code=doc.metadata.product_line_code,
        keywords=doc.keywords,
    )

async def _run_faq_logic(
    consultation_id: int,
    summary_text: str,
    summary_vector: list[float],
    full_text: str,
    product_line_code: str,
    keywords: list[str],
) -> None:
    """요약문 벡터로 FAQ top1 검색 후 hit_count 증가 또는 신규 FAQ 생성. 요약문이 비어 있으면 스킵."""
    if not summary_text.strip():
        return
    logger.info(f"FAQ 매칭 시작: {summary_text}")
    try:
        resp = await faq_similarity_search(summary_vector, keywords, product_line_code, 10)
        if resp is None:
            logger.info(f"FAQ 매칭 결과가 없습니다. 신규 FAQ 생성: {summary_text}")
            await create_and_index_faq(
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                product_line_code=product_line_code,
            )
            return
        
        faq_top10 = resp["hits"]["hits"]
        
        faq_hit, faq_score = await get_faq_top1(faq_top10)

        # 1. FAQ 매칭 결과가 없거나 유사도가 LOW_SIMILARITY_THRESHOLD 미만이면 신규 FAQ 생성
        if faq_hit is None or faq_score < LOW_SIMILARITY_THRESHOLD:
            logger.info(f"FAQ 매칭 결과가 없거나 유사도가 LOW_SIMILARITY_THRESHOLD 미만이면 신규 FAQ 생성: {faq_hit}, {faq_score}")
            await create_and_index_faq(
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                product_line_code=product_line_code,
            )

        # 2. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 이상이면 hit_count 증가
        elif faq_score >= HIGH_SIMILARITY_THRESHOLD:
            logger.info(f"FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 이상이면 hit_count 증가: {faq_hit}, {faq_score}")
            await increment_faq_hit_count(faq_hit["_id"])

        # 3. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 미만이면 LLM으로 동일 질문 여부 판별
        else:
            logger.info(f"FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 미만이면 LLM으로 동일 질문 여부 판별: {faq_hit}, {faq_score}")
            faq_question = (faq_hit.get("_source") or {}).get("question", "")
            if llm_same_question(summary_text, faq_question):
                await increment_faq_hit_count(faq_hit["_id"])
            else:
                logger.info(f"동일 질문이 아니면 신규 FAQ 생성: {faq_question}")
                await create_and_index_faq(
                    source_consultation_id=str(consultation_id),
                    summary_text=summary_text,
                    full_text=full_text,
                    product_line_code=product_line_code,
                )
    except Exception as e:
        logger.warning(f"FAQ 매칭/생성 중 오류 (상담 이력 인덱싱은 완료됨):{e}")


async def get_faq_top1(
    faq_top10: list[dict],
) -> tuple[dict | None, float]:
    """
    _id, _source가 있으면 (hit, score) 반환. 없으면 (None, 0.0) 반환.
    """
    
    hit = faq_top10[0]
    if not hit:
        return None, 0.0

    return hit, float(hit.get("_score", 0.0))