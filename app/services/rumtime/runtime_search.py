# 1. 상담사가 질문 텍스트 입력 -> 백에 전달할 데이터는? 고객정보(일반화된 것) + 질문? 일단은 질문 텍스트만.
# 2. 질문 텍스트를 임베딩, 이때 키워드는 어떻게 할건지? 하이브리드 검색? 단순 벡터 검색?
# 3. 임베딩된 질문 텍스트를 ES에서 검색
# 4. 검색 결과 점수가 0.9 이상이면 해당 faq의 답변을 출력
# 5. 검색 결과 점수가 0.65? 미만이면 관련된 답변 없습니다. 출력
# 6. 검색 결과 점수가 0.65 이상이고, 유사도가 비슷한 것이 여러 개 있을 경우 답변을 조합하여 하나의 적절한 답변 생성(RAG?), 적절한 답변이 없을 경우 관련된 답변이 없습니다. 출력.\

from loguru import logger
from app.services.common import embeddings
from app.services.rumtime.es_runtime import check_similarity
from app.services.common.llm_service import llm_generate_rag_answer

async def runtime_search(question_text: str) -> str:
   """
   상담사가 입력한 질문 텍스트를 임베딩 및 키워드 추출? 하여 ES에서 유사도 검사.
   => 검색 결과 점수가 0.9 이상이면 해당 faq의 답변을 출력
   => 검색 결과 점수가 0.65? 미만이면 관련된 답변 없습니다. 출력
   => 검색 결과 점수가 0.65 이상이고, 유사도가 비슷한 것이 여러 개 있을 경우 답변을 조합하여 하나의 적절한 답변 생성(RAG?),
      적절한 답변이 없을 경우 관련된 답변이 없습니다. 출력.
   """
   logger.info(f"상담사가 입력한 질문 텍스트: {question_text}")

   try:
      # 질문 텍스트 임베딩
      vector = await embeddings.get_embedding(question_text)

      # ES에서 유사도 검사
      response = await check_similarity(question_text, vector)
      logger.info(f"ES 검색 결과: {response}")

      if response is None:
         return "관련된 가이드가 없습니다."

      if response['hits']['total']['value'] == 0:
         return "관련된 가이드가 없습니다."

      if response['hits']['total']['value'] > 0:
         hits = response['hits']['hits']
         # 유사도가 0.9 이상이면 해당 faq의 답변을 출력
         if hits[0]['_score'] >= 0.9:
            return hits[0]['_source']['answer']

         # 유사도가 0.65 미만이면 관련된 답변이 없습니다. 출력
         elif hits[0]['_score'] < 0.6:
            return "관련된 가이드가 없습니다."

         # 유사도가 0.65이상, 0.9 미만인 모든 항목은 llm을 통해 답변 조합. 관련 없을 경우 관련된 답변이 없습니다. 출력.
         else:
            retrieved_faqs = [] # 유사도가 0.65이상, 0.9 미만인 모든 항목의 FAQ 리스트
            for hit in hits:
               if hit['_score'] >= 0.6 and hit['_score'] < 0.9:
                  retrieved_faqs.append({
                    "question": hit['_source'].get('question'),
                    "answer": hit['_source'].get('answer'),
                    "score": round(hit['_score'], 2) # 소수점 둘째자리까지 반올림해서 깔끔하게
                })
            if retrieved_faqs:
               logger.info(f"LLM 답변 조합 진행: {retrieved_faqs}")
               answer = await llm_generate_rag_answer(question_text, retrieved_faqs[:5])
               logger.info(f"LLM 답변 조합 결과: {answer}")
               return answer
            else:
               return "관련된 가이드가 없습니다."

   except Exception as e:
      logger.error(f"실시간 검색 중 오류 발생: {e}")
      raise e