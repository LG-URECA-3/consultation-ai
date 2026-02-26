from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel

from app.core.infrastructure import engine
from app.api.es_index import router as es_index_router

# 1. Lifespan 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [Startup] 테이블 자동 생성 (hibernate ddl-auto: update와 유사)
    async with engine.begin() as conn:
        # models 폴더에 정의된 모든 SQLModel 테이블을 DB에 생성
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield
    
    # [Shutdown] 커넥션 풀 정리
    await engine.dispose()

# 2. FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Consultation AI API",
    description="상담 요약 및 벡터 검색을 제공하는 AI 서비스",
    version="0.1.0",
    lifespan=lifespan
)

# 3. 라우터 등록
app.include_router(es_index_router)

# 4. 기본 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """앱 상태를 확인하는 헬스체크용 API입니다."""
    return {"status": "healthy", "message": "Consultation AI 서버가 작동 중입니다!"}

@app.get("/")
async def root():
    return {"message": "AI 상담 지원 시스템 API에 오신 것을 환영합니다."}