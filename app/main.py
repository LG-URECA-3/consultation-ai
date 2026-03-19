from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import SQLModel
from loguru import logger
import asyncio
from app.kafka.consume import consumer
from app.api.routes.consultation_histories import router as consultation_histories_router
from app.core.config import settings
from app.core.infrastructure import engine, es_client

# 1. Lifespan 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
        consumer_task = asyncio.create_task(consumer())
        logger.info("Kafka Consumer가 백그라운드에서 시작되었습니다.")
        yield
        logger.info("Kafka Consumer 종료 중...")
        await consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Kafka Consumer가 안전하게 종료되었습니다.")
        finally:
            await engine.dispose()

# 2. FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Consultation AI API",
    description="상담 요약 및 벡터 검색을 제공하는 AI 서비스",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/fastapi/docs",
    redoc_url="/fastapi/redoc",
    openapi_url="/fastapi/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:.*|http://127\.0\.0\.1:.*|https://.*\.ap-northeast-2\.elb\.amazonaws\.com",
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(consultation_histories_router)

# 3. 기본 헬스체크 엔드포인트
@app.get("/fastapi/health")
async def health_check():
    """앱 상태를 확인하는 헬스체크용 API입니다."""
    return {"status": "healthy", "message": "Consultation AI 서버가 작동 중입니다!"}


@app.get("/fastapi/health/ready", status_code=status.HTTP_200_OK)
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


@app.get("/fastapi")
async def root():
    return {"message": "AI 상담 지원 시스템 API에 오신 것을 환영합니다."}