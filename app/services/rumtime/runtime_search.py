# 1. 상담사가 질문 텍스트 입력 -> 백에 전달할 데이터는? 고객정보(일반화된 것) + 질문? 일단은 질문 텍스트만.
# 2. 질문 텍스트를 임베딩, 이때 키워드는 어떻게 할건지? 하이브리드 검색? 단순 벡터 검색?
# 3. 임베딩된 질문 텍스트를 ES에서 검색
# 4. 답변을 조합하여 하나의 적절한 답변 생성(RAG?), 적절한 답변이 없을 경우 관련된 답변이 없습니다. 출력.

from loguru import logger
from app.services.common import embeddings
from app.services.rumtime.es_runtime import check_similarity
from app.services.common.llm_service import llm_generate_rag_answer
from app.schemas.runtime_search_resonse import RuntimeSearchResponse
from app.services.data.data_processor import expand_query, load_expansion_rules

async def runtime_search(question_text: str) -> RuntimeSearchResponse:
   """
   상담사가 입력한 질문 텍스트를 임베딩 및 키워드 추출? 하여 ES에서 유사도 검사.
   => 검색 결과를 LLM에 넣어 답변 생성(RAG)
   => 검색 결과를 LLM에 넣어서 답변 조합하여 출력. 고객에게 즉시 안내할 수 있도록 친절하고 명확한 문장으로 작성.
      적절한 답변이 없을 경우 관련된 답변이 없습니다. 출력. -> 이런 답변을 찾으셨나요? 진행.
   """
   logger.info(f"상담사가 입력한 질문 텍스트: {question_text}")

   expanded_query = expand_query(question_text, load_expansion_rules())

   try:
      # 질문 텍스트 임베딩
      vector = await embeddings.get_embedding(expanded_query)

      # ES에서 유사도 검사
      response = await check_similarity(expanded_query, vector)
      logger.info(f"ES 검색 결과: {response}")
      total_hits = response['hits']['total']['value']

      if response is None:
         return RuntimeSearchResponse(answer="관련된 답변이 존재하지 않습니다. 도움이 필요하시다면 상담사 연결을 진행해주세요.", retrieved_faqs=[])

      if total_hits == 0:
         return RuntimeSearchResponse(answer="관련된 답변이 존재하지 않습니다. 도움이 필요하시다면 상담사 연결을 진행해주세요.", retrieved_faqs=[])

      if total_hits > 0:
         hits = response['hits']['hits']
         # 유사도가 0.5 이상이면 retrieved_faqs 리스트에 추가.
         retrieved_faqs = []
         for hit in hits:
            if len(retrieved_faqs) >= 15:
               break

            retrieved_faqs.append({
               "faq_id": hit['_source'].get('faq_id'),
               "question": hit['_source'].get('question'),
               "answer": hit['_source'].get('answer'),
               # "score": round(hit['_score'], 2) # 소수점 둘째자리까지 반올림해서 깔끔하게 -> LLM 판단 정확도 위해 제거.
            })

         
         if retrieved_faqs:
            # logger.info(f"LLM 답변 조합 진행: {retrieved_faqs}")
            response = await llm_generate_rag_answer(question_text, retrieved_faqs)
            logger.info(f"LLM 답변 조합 결과: {response}")

            faq_dict = {f['faq_id']: f for f in retrieved_faqs}
            referenced_faqs = [faq_dict[faq_id] for faq_id in response.referenced_faq_ids if faq_id in faq_dict]

            return RuntimeSearchResponse(answer=response.answer, retrieved_faqs=referenced_faqs) # 최대 3개까지만 반환
         else:
            return RuntimeSearchResponse(answer="관련된 답변이 존재하지 않습니다. 도움이 필요하시다면 상담사 연결을 진행해주세요.", retrieved_faqs=[]) # 관련된 가이드가 없을 경우 빈 리스트 반환

   except Exception as e:
      logger.error(f"실시간 검색 중 오류 발생: {e}")
      raise e