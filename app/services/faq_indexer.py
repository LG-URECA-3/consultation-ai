
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
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.faq_knowledge_base import (
    llm_same_question,
)
from app.services.es_faq import faq_similarity_search, increment_faq_hit_count
from app.schemas.consultation_history_doc import ConsultationHistoryDoc
from app.services import embeddings
from app.services.es_faq import setup_faq_index_if_not_exists
from app.services.faq_knowledge_base import _llm_generate_faq_question_answer
from app.models.kb_search_sync import KbSearchSync
from app.crud.crud_kb_search_sync import upsert_kb_search_sync
from app.models.enums import IndexStatus
import uuid
from datetime import datetime, timezone
from app.schemas.faq_doc import FaqDoc
from app.core.infrastructure import AsyncSessionLocal, es_client
from app.services.es_faq import FAQ_INDEX
from app.models.knowledge_base import KnowledgeBase
from app.crud.crud_knowledge_base import insert_knowledge_base, update_knowledge_base_hit_count_and_last_hit_at

HIGH_SIMILARITY_THRESHOLD = 0.95
LOW_SIMILARITY_THRESHOLD = 0.6

async def run_faq_from_consultation_doc(doc: ConsultationHistoryDoc) -> None:
    """
    Step 2: ConsultationHistoryDoc 기준으로 FAQ top1 매칭 후 hit_count 증가 또는 신규 FAQ 생성.
    """
    logger.info(f"유사도 검사 시작. consultation_id: {doc.consultation_id}")
    async with AsyncSessionLocal() as session:
        try:
            await _run_faq_logic(
                session=session,
                consultation_id=doc.consultation_id,
                summary_text=doc.summary_text,
                summary_vector=doc.summary_vector,
                full_text=doc.full_text,
                product_line_code=doc.metadata.product_line_code.value,
                keywords=doc.keywords,
            )
            logger.info(f"FAQ 생성 로직 성공!")
            await session.commit()

        except Exception as e:
            logger.error(f"FAQ 매칭 중 오류 발생: {e}")
            await session.rollback()
            raise e
            

async def _run_faq_logic(
    session: AsyncSession,
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
    logger.info(f"summary_text로 FAQ 유사도 검색 시작. summary_text: {summary_text}")
    try:
        resp = await faq_similarity_search(summary_vector, keywords, product_line_code, 10)
        if resp is None:
            logger.info(f"인덱스가 없거나 FAQ 매칭 결과 없음. 신규 FAQ 생성: {summary_text}")
            await create_faq_and_save_kb_to_db(
                session=session,
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                product_line_code=product_line_code,
            )
            return
        
        faq_top10 = resp["hits"]["hits"]
        
        if not faq_top10:
            logger.info(f"인덱스가 있지만 FAQ 매칭 결과가 없습니다. 신규 FAQ 생성: {summary_text}")
            await create_faq_and_save_kb_to_db(
                session=session,
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                product_line_code=product_line_code,
            )
            return
        
        faq_hit, faq_score = await get_faq_top1(faq_top10)

        # 1. FAQ 매칭 결과가 없거나 유사도가 LOW_SIMILARITY_THRESHOLD 미만이면 신규 FAQ 생성
        if faq_hit is None or faq_score < LOW_SIMILARITY_THRESHOLD:
            logger.info(f"FAQ 매칭 결과가 없거나 유사도가 LOW_SIMILARITY_THRESHOLD 미만이면 신규 FAQ 생성: {faq_hit}, {faq_score}")
            await create_faq_and_save_kb_to_db(
                session=session,
                source_consultation_id=str(consultation_id),
                summary_text=summary_text,
                full_text=full_text,
                product_line_code=product_line_code,
            )

        # 2. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 이상이면 hit_count 증가
        elif faq_score >= HIGH_SIMILARITY_THRESHOLD:
            logger.info(f"FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 이상이면 hit_count 증가: {faq_hit}, {faq_score}")
            await increase_hit_count(session, faq_hit["_id"])

        # 3. FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 미만이면 LLM으로 동일 질문 여부 판별
        else:
            logger.info(f"FAQ 매칭 결과가 있고 유사도가 HIGH_SIMILARITY_THRESHOLD 미만이면 LLM으로 동일 질문 여부 판별: {faq_hit}, {faq_score}")
            faq_question = (faq_hit.get("_source") or {}).get("question", "")
            if llm_same_question(summary_text, faq_question):
                await increase_hit_count(session, faq_hit["_id"])
            else:
                logger.info(f"동일 질문이 아니면 신규 FAQ 생성: {faq_question}")
                await create_faq_and_save_kb_to_db(
                    session=session,
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


async def create_faq_and_save_kb_to_db(
    session: AsyncSession,
    source_consultation_id: str,
    summary_text: str,
    full_text: str,
    product_line_code: str,
):
    """
    LLM으로 생성된 FAQ를 ES에 저장. 저장된 FAQ를 DB에 기록.
    """
    try:
        faq_doc = await create_and_index_faq(
            source_consultation_id=source_consultation_id,
            summary_text=summary_text,
            full_text=full_text,
            product_line_code=product_line_code,
        )

        knowledge_base = KnowledgeBase(
            faq_id=faq_doc.faq_id,
            product_line_code=product_line_code,
            request=faq_doc.question,
            answer=faq_doc.answer,
            hit_count=faq_doc.hit_count,
            last_hit_at=datetime.now(),
        )
        kb_response = await insert_knowledge_base(session, knowledge_base)

        kb_search_sync = KbSearchSync(
            kb_id=kb_response.kb_id,
            es_doc_id=faq_doc.faq_id,
            index_alias=FAQ_INDEX,
            index_status=IndexStatus.INDEXED,
            source_updated_at=kb_response.created_at,
            last_indexed_at=faq_doc.created_at,
            last_attempt_at=faq_doc.created_at,
            retry_count=0,
            last_error=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        await upsert_kb_search_sync(session, kb_search_sync)
    except Exception as e:
        logger.error(f"FAQ 생성 및 KB 저장 중 오류 발생: {e}")
        raise e

async def create_and_index_faq(
    source_consultation_id: str,
    summary_text: str,
    full_text: str,
    product_line_code: str,
) -> FaqDoc:
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
    created_at = datetime.now(timezone.utc)

    doc = FaqDoc(
        faq_id=faq_id,
        source_consultation_id=source_consultation_id,
        question=question,
        answer=answer,
        question_vector=question_vector,
        product_line_code=product_line_code,
        hit_count=1,
        created_at=created_at,
    )
    logger.info(f"FAQ 문서 생성 완료: {faq_id}")
    try:
        document = doc.model_dump(mode="json")
        es_response = await es_client.index(index=FAQ_INDEX, id=faq_id, document=document)
        logger.success(f"FAQ 생성 완료: {dict(es_response)}")
        return doc
    except Exception as e:
        logger.error(f"FAQ 생성 중 ES 오류 발생: {e}")
        raise e


async def increase_hit_count(session: AsyncSession, faq_id: str):
    """
        ES FAQ 및 DB knowledge_base hit_count를 1 증가시킵니다.
    """
    try:
        await increment_faq_hit_count(faq_id)
        await update_knowledge_base_hit_count_and_last_hit_at(session, faq_id)

    except Exception as e:
        logger.error(f"ES FAQ 및 DB knowledge_base hit_count 증가 중 오류 발생: {e}")
        raise e