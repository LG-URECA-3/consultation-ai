import aiofiles
import json
import os
from datetime import datetime
from loguru import logger

# 1. 현재 파일의 위치: app/services/common/dataset_logger.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 

# 2. 한 단계 위로 이동: app/services/
SERVICES_DIR = os.path.dirname(CURRENT_DIR)

# 3. 최종 목적지: app/services/data/faq_saved_dataset.jsonl
DATA_DIR = os.path.join(SERVICES_DIR, "data")
DATASET_PATH = os.path.join(DATA_DIR, "faq_saved_dataset.jsonl")

async def save_to_saved_dataset(
    faq_id: str, 
    source_consultation_id: str,
    faq_question: str,
    faq_answer: str,
) -> None:
    """
    RAG 평가를 위한 faq 데이터를 파일에 비동기로 추가 저장합니다.
    기존 파일이 있으면 아래에 이어서 작성(Append)합니다.
    """
    try:
        # 1. 폴더가 없는 경우 자동으로 생성
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            logger.info(f"폴더가 존재하지 않아 생성했습니다: {DATA_DIR}")

        record = {
            "faq_id": faq_id,
            "faq_question": faq_question.strip(),
            "faq_answer": faq_answer.strip(),
            "source_consultation_id": source_consultation_id,
            "created_at": datetime.now().isoformat() # 언제 저장되었는지 기록 (권장)
        }

        # 2. 'a' 모드는 파일이 없으면 생성하고, 있으면 끝에 내용을 덧붙입니다.
        async with aiofiles.open(DATASET_PATH, mode='a', encoding='utf-8') as f:
            # ensure_ascii=False로 설정해야 한글이 깨지지 않고 저장됩니다.
            line = json.dumps(record, ensure_ascii=False)
            await f.write(line + "\n")
            
        logger.debug(f"faq 데이터 기록 완료 (누적): {faq_id}")
        
    except Exception as e:
        logger.error(f"faq 데이터 저장 중 오류 발생: {str(e)}")