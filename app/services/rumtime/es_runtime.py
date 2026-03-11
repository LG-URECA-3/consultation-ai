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
        "size": k,
        "query": {
            "script_score": {
                # 1. 베이스 쿼리: 키워드가 하나라도 걸리는 것들 + 상품군 필터
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": input_text,
                                    "fields": ["question", "answer"], 
                                    "operator": "or"
                                }
                            }
                        ],
                        # "filter": [{"term": {"product_line_code": product_line_code}}] # 필요시 활성화
                    }
                },
                # 2. 정교한 점수 계산 로직 (Painless Script)
                # 벡터 유사도 계산 -> 키워드 정규화(k_factor = 2.0 적용) -> 가중치 합산(7:3 비율) -> 보정 로직(벡터가 확실하면(0.85 이상) 점수를 0.9 위로 펌핑)
                "script": {
                    "source": """
                        double v_sim = (cosineSimilarity(params.query_vector, 'question_vector') + 1.0) / 2.0;
                        double n_bm25 = _score / (_score + 2.0);
                        
                        double combined = (v_sim * 0.7) + (n_bm25 * 0.3);
                        
                        if (v_sim >= 0.85) {
                            return Math.max(0.9, combined);
                        }
                        
                        return combined;
                    """,
                    "params": {"query_vector": input_vector}
                }
            }
        },
        # 가치 증명을 위한 메타데이터 포함
        "_source": ["faq_id", "question", "answer", "hit_count", "created_at"]
    }

    try:
        response = await es_client.search(
            index=FAQ_INDEX,
            body=search_request,
        )
        logger.info(f"ES 검색 완료! 최대 유사도: {response['hits']['total']}")
        return response
    except Exception as e:
        logger.error(f"ES 검색 실패: {e}")
        raise