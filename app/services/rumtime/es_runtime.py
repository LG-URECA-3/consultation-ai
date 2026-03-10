from loguru import logger
from app.services.processor.es_faq import FAQ_INDEX
from app.core.infrastructure import es_client

async def check_similarity(input_text: str, input_vector: list[float], k: int = 5):
    """
    FAQ 인덱스에 하이브리드 유사도 검색 진행하여 결과 반환.
    input_vector로 kNN+keyword 검색, top k 반환.
    - 검색: 가중치(키워드+벡터) 하이브리드 검색
    """
    if not await es_client.indices.exists(index=FAQ_INDEX):
        logger.warning(f"인덱스가 존재하지 않습니다: {FAQ_INDEX}")
        return None

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
                                                    "query": input_text,
                                                    "fields": ["summary_text", "question", "answer"],
                                                    "operator": "or",
                                                    # "minimum_should_match": "50%" # 키워드 중 최소 절반은 맞아야함.
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
                                "field": "question_vector",
                                "query_vector": input_vector, # 입력된 텍스트 임베딩-저장된 텍스트 임베딩 비교.
                                "k": k,
                                "num_candidates": 50
                            }
                        },
                        "weight": 0.7,
                        "normalizer": "minmax"
                    }
                ],
                "rank_window_size": k
            }
        },
        "_source": ["faq_id", "question", "answer"]
    }

    try:
        response = await es_client.search(
            index=FAQ_INDEX,
            retriever=search_request["retriever"],
            source=search_request["_source"],
        )
        logger.info(f"ES 검색 완료! 최대 유사도: {response['hits']['total']}")
        return response
    except Exception as e:
        logger.error(f"ES 검색 실패: {e}")
        raise