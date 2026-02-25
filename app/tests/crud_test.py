import asyncio
from app.core.infrastructure import get_session, engine # 세션 제너레이터 경로에 맞게 수정
from app.crud import crud_consultation, crud_consultation_message, crud_consultation_record
from loguru import logger

# 로컬 테스트용 비동기 메인 함수
async def run_test():
    async for session in get_session():
        logger.info("--- 데이터 조회 테스트 시작 ---")
        
        # 테스트할 상담 ID (DB에 있는 실제 ID로 변경)
        test_id = 3
        
        # 1. 단건 조회 테스트 (session.get 활용한 부분)
        consultation = await crud_consultation.get_consultation_by_id(session, test_id)
        
        if consultation:
            logger.success(f"조회 성공!: {consultation}")
        else:
            logger.error(f"데이터를 찾을 수 없습니다. (ID: {test_id})")

        # 2. 메시지 내역 조회
        messages = await crud_consultation_message.get_messages_by_consultation_id(session, test_id)
        logger.info(f"조회된 메시지 개수: {len(messages)}개")

        # 3. 요약 기록 조회
        record = await crud_consultation_record.get_record_by_consultation_id(session, test_id)
        if record:
            logger.info(f"요약 기록: {record.summary_text[:20]}...")

    await engine.dispose()

if __name__ == "__main__":
    # 이벤트 루프를 강제로 실행하여 비동기 함수 테스트
    asyncio.run(run_test())