import os
import sys
import asyncio
import json
from loguru import logger

# 1. 경로 설정 (app 패키지를 찾기 위함)
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 2. 필요한 모듈 임포트
from app.services.processor.post_processor import post_processing
from app.core.infrastructure import es_client

async def create_benchmark_data_sequential(start_id: int, limit: int):
    """
    병렬 처리 없이 1개씩 순차적으로 실행하여 안정성을 확보합니다.
    """
    logger.info(f"🚀 FAQ 데이터 생성을 시작합니다. (순차 실행 모드 / 대상: {limit}개)")

    for c_id in range(start_id, limit + 1):
        try:
            # 한 번에 하나씩 실행 (await로 결과가 나올 때까지 대기)
            await post_processing(consultation_id=c_id)
            
            if c_id % 10 == 0:
                logger.info(f"⏳ 진행 중... ({c_id}/{limit})")
                
        except Exception as e:
            logger.error(f"❌ ID {c_id} 처리 중 실패: {e}")
            # 특정 ID에서 실패해도 다음으로 넘어가도록 계속 진행

    logger.success(f"✅ 모든 데이터 생성 완료! (총 {limit}개 처리)")

async def create_testdata():
    try:
        await create_benchmark_data_sequential(start_id=51, limit=100)
    finally:
        # 모든 루프가 끝난 뒤 클라이언트 종료
        logger.info("🧹 ES 클라이언트를 종료합니다...")
        await es_client.close()
        # Windows 루프 종료 이슈 방지를 위한 아주 짧은 대기
        await asyncio.sleep(0.5)

# if __name__ == "__main__":
#     asyncio.run(create_testdata())