import asyncio
from openai import OpenAI
from loguru import logger
from app.core.config import settings
from app.core.infrastructure import openai_client, es_client
import pytest

@pytest.mark.asyncio
async def test_openai_embedding_search():
    index_name = "connection_test_vector"
    test_text = "상담원이 너무 친절해서 기분이 좋네요."
    # test_text = "상담원이 너무 불친절해요."
    
    try:
        # 2. OpenAI 임베딩 생성 (text-embedding-3-small 기준)
        embed_res = openai_client.embeddings.create(
            input=test_text,
            model="text-embedding-3-small" #
        )
        vector = embed_res.data[0].embedding
        dims = len(vector) # 보통 1536 차원
        logger.success(f"OpenAI 임베딩 생성 성공 (차원: {dims})")

        # 3. ES 인덱스 생성 (벡터 매핑 포함)
            
        if not await es_client.indices.exists(index=index_name):
            await es_client.indices.create(
            index=index_name,
            mappings={
                "properties": {
                    "content": {"type": "text"},
                    "content_vector": {
                        "type": "dense_vector",
                        "dims": dims, # OpenAI 모델 차원과 정확히 일치해야 함
                        "index": True,
                        "similarity": "cosine" # 코사인 유사도 방식
                        }
                    }
                }
            )
            logger.info(f"✨ '{index_name}' 인덱스를 새로 생성했습니다.")
        else:
            # 이미 있다면 삭제하지 않고 그대로 사용합니다.
            logger.info(f"✅ '{index_name}' 인덱스가 이미 존재합니다. 데이터를 누적합니다.")

        # 4. 벡터 데이터 저장
        await es_client.index(
            index=index_name,
            document={"content": test_text, "content_vector": vector}
        )
        await es_client.indices.refresh(index=index_name)
        logger.success("ES에 OpenAI 벡터 저장 완료")

        # 5. 유사도 검색 테스트
        search_res = await es_client.search(
            index=index_name,
            knn={
                "field": "content_vector",
                "query_vector": vector,
                "k": 1,
                "num_candidates": 10
            }
        )
        
        hit = search_res['hits']['hits'][0]
        logger.success(f"검색 결과: {hit['_source']['content']} (유사도 점수: {hit['_score']})")

    except Exception as e:
        logger.error(f"통합 테스트 실패: {e}")
    finally:
        await es_client.close()

if __name__ == "__main__":
    asyncio.run(test_openai_embedding_search())