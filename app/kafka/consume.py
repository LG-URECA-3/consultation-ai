from app.core.config import settings
from aiokafka import AIOKafkaConsumer
import json
from loguru import logger
from app.services.post_processor import post_processing

async def setup_kafka_consumer():
    kafka_consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP_ID,
        auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        enable_auto_commit=False,
        session_timeout_ms=settings.KAFKA_SESSION_TIMEOUT_MS
    )
    return kafka_consumer

async def consumer():
    kafka_consumer = await setup_kafka_consumer()
    await kafka_consumer.start()
    try:
        async for message in kafka_consumer:
            consultation_id = message.value
            # 여기서 consultation_search_sync 테이블 생성 및 상태값 저장(PENDING)
            logger.info(f"consultation_id 수신: {consultation_id}")

            try:
                doc = await post_processing(consultation_id)

                if doc is not None:
                    # 여기서 consultation_search_sync 테이블 상태값 저장(INDEXED)
                    await kafka_consumer.commit()
                    logger.info(f"후처리 로직 성공!")
            except Exception as e:
                logger.error(f"후처리 로직 실패: {e}")
                # 여기서 consultation_search_sync 테이블 상태값 저장(FAILED)
                continue
    finally:
        await kafka_consumer.stop()