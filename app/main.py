from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from loguru import logger
import asyncio
from app.kafka.consume import consumer
from app.api.routes.consultation_histories import router as consultation_histories_router
from app.core.infrastructure import engine

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
    lifespan=lifespan
)

app.include_router(consultation_histories_router)

# 3. 기본 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """앱 상태를 확인하는 헬스체크용 API입니다."""
    return {"status": "healthy", "message": "Consultation AI 서버가 작동 중입니다!"}

@app.get("/")
async def root():
    return {"message": "AI 상담 지원 시스템 API에 오신 것을 환영합니다."}