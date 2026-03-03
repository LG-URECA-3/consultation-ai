
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
from app.core.infrastructure import es_client

async def check_similarity(summary_vector: list[float], keywords: list[str], product_line_code: str):
    """
    1. 검색: 필터(상품군) + 가중치(키워드+벡터) 하이브리드 검색
    2. 판단: 점수 구간별 자동화/검증/생성 분기
    """
    keyword_query = " ".join(keywords)

    search_request = {
        "retriever": {
            "linear": {
                "retrievers": [
                    {
                        "retriever": {
                            "standard": {
                                "query": {
                                    "bool": {
                                        "must": [
                                            {
                                                "multi_match": {
                                                    "query": keyword_query, # LLM이 뽑아준 짧은 키워드
                                                    "fields": ["summary_text", "question", "answer"],
                                                    "operator": "or",
                                                    "minimum_should_match": "50%" # 키워드 중 최소 절반은 맞아야함.
                                                }
                                            }
                                        ],
                                        "filter": [
                                            {
                                                "term": {
                                                    "product_line_code": product_line_code
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "weight": 0.3,
                        "normalizer": "minmax"
                    },
                    {
                        "retriever": {
                            "knn": {
                                "field": "summary_vector",
                                "query_vector": summary_vector, # 저장된 요약 임베딩-입력된 요약 임베딩 비교.
                                "k": 5,
                                "num_candidates": 50
                            }
                        },
                        "weight": 0.7,
                        "normalizer": "minmax"
                    },
                    {

                    }
                ],
                "rank_window_size": 10
            }
        },
        "_source": ["faq_id", "question"]
    }

    try:
        response = await es_client.search(
            index="consultation_faq",
            body=search_request
        )
        hits = response["hits"]["hits"]

        if not hits:
            return hits

    except Exception as e:
        logger.error(f"ES 검색 실패: {e}")
        raise
    finally:
        return response