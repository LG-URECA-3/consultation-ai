from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import SQLModel

from app.api.routes.consultation_histories import router as consultation_histories_router
from app.core.config import settings
from app.core.infrastructure import engine, es_client

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

app.include_router(consultation_histories_router)

# 3. 기본 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """앱 상태를 확인하는 헬스체크용 API입니다."""
    return {"status": "healthy", "message": "Consultation AI 서버가 작동 중입니다!"}


@app.get("/health/ready", status_code=status.HTTP_200_OK)
async def health_ready():
    """
    Readiness: DB, Elasticsearch, Redis 연결 상태를 검사합니다.
    모두 정상이면 200, 하나라도 실패하면 503을 반환합니다.
    Redis는 REDIS_HOST가 설정된 경우에만 검사합니다.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e!s}"
        all_ok = False

    # Elasticsearch
    try:
        await es_client.ping()
        checks["elasticsearch"] = "ok"
    except Exception as e:
        checks["elasticsearch"] = f"error: {e!s}"
        all_ok = False

    # Redis (설정된 경우에만)
    if settings.REDIS_HOST:
        try:
            import redis.asyncio as redis_async

            r = redis_async.Redis(
                host=settings.REDIS_HOST,
                port=6379,
                password=settings.REDIS_PASSWORD or None,
                socket_connect_timeout=2,
            )
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e!s}"
            all_ok = False
    else:
        checks["redis"] = "not_configured"

    if not all_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "message": "One or more dependencies are unavailable",
                "checks": checks,
            },
        )
    return {
        "status": "ready",
        "message": "All dependencies are available",
        "checks": checks,
    }


@app.get("/")
async def root():
    return {"message": "AI 상담 지원 시스템 API에 오신 것을 환영합니다."}