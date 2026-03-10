from app.core.infrastructure import es_client
from loguru import logger
from app.core.config import settings

FAQ_INDEX = "faq_knowledge_base"

async def setup_faq_index_if_not_exists() -> None:
    """faq_knowledge_base 인덱스가 없으면 question_vector 매핑으로 생성."""
    if await es_client.indices.exists(index=FAQ_INDEX):
        return

    logger.info(f"인덱스 '{FAQ_INDEX}' 생성 중...")

    index_settings = {
        "settings": {
            "index": {
                "refresh_interval": "1s"
            }
        },
        "mappings": {
            "properties": {
                "faq_id": {"type": "keyword"},
                "source_consultation_id": {"type": "long"},
                "question": {"type": "text"},
                "answer": {"type": "text"},
                "question_vector": {
                    "type": "dense_vector",
                    "dims": settings.EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine",
                },
                "product_line_code": {"type": "keyword"},
                "hit_count": {"type": "integer"},
                "created_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time"},
            }
        }
    }
    await es_client.indices.create(index=FAQ_INDEX, body=index_settings)
    logger.info(f"인덱스 '{FAQ_INDEX}' 생성 완료")


# es에 유사도 하이브리드 검색 함수
async def faq_similarity_search(summary_vector: list[float], keywords: list[str], product_line_code: str, k: int = 10):
    """
    상담 요약문을 바탕으로 FAQ 인덱스에 유사한 내용이 존재하는지 검색.
    summary_vector로 kNN+keyword 검색, top k 반환.
    1. 검색: 필터(상품군) + 가중치(키워드+벡터) 하이브리드 검색
    2. 판단: 점수 구간별 자동화/검증/생성 분기
    """
    keyword_query = " ".join(keywords)

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
                                                    "query": keyword_query, # LLM이 뽑아준 짧은 키워드
                                                    "fields": ["summary_text", "question", "answer"],
                                                    "operator": "or",
                                                    # "minimum_should_match": "50%" # 키워드 중 최소 절반은 맞아야함.
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
                                "field": "question_vector",
                                "query_vector": summary_vector, # 저장된 요약 임베딩-입력된 요약 임베딩 비교.
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
        "_source": ["faq_id", "question"]
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
        return None


async def increment_faq_hit_count(faq_id: str) -> None:
    """기존 FAQ 문서의 hit_count를 1 증가 (ES update script)."""
    try:
        await es_client.update(
                index=FAQ_INDEX,
                id=faq_id,
                script={"source": "ctx._source.hit_count += 1", "lang": "painless"},
            )
        logger.success(f"FAQ hit_count 증가 완료: {faq_id}")
    except Exception as e:
        logger.error(f"FAQ hit_count 증가 중 ES 오류 발생: {e}")
        raise e