import asyncio
from datetime import datetime
from sqlalchemy import text
from pydantic import BaseModel
from loguru import logger
import pytest

# 우리가 만든 설정과 인프라 임포트
from app.core.config import settings
from app.core.infrastructure import engine, exaone_client, es_client, get_session

class TestResponse(BaseModel):
    message: str

@pytest.mark.asyncio
async def test_mysql():
    """MySQL 연결 테스트 (SELECT 1)"""
    try:
        async for session in get_session():
            result = await session.execute(text("SELECT * from users where user_id = 1"))
            logger.success(f"MySQL 연결 성공! {result}")
    except Exception as e:
        logger.error(f"MySQL 연결 실패: {e}")

@pytest.mark.asyncio
async def test_elasticsearch():
    """Elasticsearch: 데이터 삽입 및 조회 풀 플로우 테스트"""
    index_name = "connection_test_idx"
    doc_id = "test_1"
    sample_doc = {
        "title": "인프라 통합 테스트",
        "content": "엘라스틱서치와 Kibana 연동 확인용 데이터입니다.",
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        # 데이터 삽입 (Index)
        await es_client.index(index=index_name, id=doc_id, document=sample_doc)
        
        # 즉시 조회를 위한 리프레시
        await es_client.indices.refresh(index=index_name)
        
        # 데이터 조회 (Get)
        res = await es_client.get(index=index_name, id=doc_id)
        if res.get('found'):
            logger.success(f"Elasticsearch: 데이터 삽입 및 조회 성공 (ID: {doc_id}, 문서: {res['_source']})")
        
    except Exception as e:
        logger.error(f"Elasticsearch: 플로우 테스트 실패 - {e}")

@pytest.mark.asyncio
async def test_friendli_ai():
    """Friendli AI(EXAONE) 응답 테스트"""
    try:
        # K-EXAONE 모델을 사용하여 간단한 인사말 요청
        response = exaone_client.chat.completions.create(
            model=settings.FRIENDLI_MODEL_ID,
            messages=[{"role": "user", "content": "안녕! 연결 테스트 중이야. 짧게 응답해줘."}],
            response_model=TestResponse
        )
        logger.success(f"Friendli AI 응답 성공: {response.message}")
    except Exception as e:
        logger.error(f"Friendli AI 연결 실패: {e}")


@pytest.mark.asyncio
async def run_all_tests():
    logger.info("인프라 연결 테스트를 시작합니다...")
    await asyncio.gather(
        test_mysql(),
        test_elasticsearch(),
        test_friendli_ai()
    )
    logger.info("🏁 테스트가 완료되었습니다.")

    await es_client.close()  # ES 연결 종료
    await engine.dispose()   # DB 커넥션 풀 종료

if __name__ == "__main__":
    asyncio.run(run_all_tests())