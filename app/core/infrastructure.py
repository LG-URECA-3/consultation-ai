import instructor
from openai import OpenAI
from typing import AsyncGenerator
from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# DataSource
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,           # 실행되는 SQL을 로그로 출력
    pool_pre_ping=True,  # 커넥션 유효성 자동 체크
)

# SessionFactory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# OpenAI
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Friendli AI (K-EXAONE) + Instructor Wrapper
exaone_client = instructor.from_openai(
    OpenAI(
        base_url=settings.FRIENDLI_BASE_URL,
        api_key=settings.FRIENDLI_TOKEN,
    )
)

# Elasticsearch
es_client = AsyncElasticsearch(settings.ES_URL, request_timeout=30)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # yield 이후 세션 닫기
            await session.close()
