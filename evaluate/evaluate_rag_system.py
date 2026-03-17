import os
import sys
import asyncio
import pandas as pd
import json
from loguru import logger
from dotenv import load_dotenv

# 1. 경로 및 환경 변수 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
dotenv_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path)

if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.services.rumtime.runtime_search import runtime_search

async def run_evaluation(golden_set_path: str):
    # 결과 저장 경로
    save_dir = os.path.join(root_dir, "result")
    os.makedirs(save_dir, exist_ok=True)
    temp_path = os.path.join(save_dir, "temp_results.jsonl")

    # [Checkpoint] 기존 진행 내역 로드
    processed_questions = set()
    rows = []
    if os.path.exists(temp_path):
        with open(temp_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    rows.append(data)
                    processed_questions.add(data["question"])
        logger.info(f"체크포인트 로드: {len(processed_questions)}건 완료. 이어서 시작합니다.")

    # 골든셋 로드
    full_path = os.path.abspath(os.path.join(root_dir, golden_set_path))
    with open(full_path, "r", encoding="utf-8") as f:
        golden_set = [json.loads(line) for line in f]

    # 2. 검색 루프 (순수 검색 성능 측정)
    for i, case in enumerate(golden_set):
        question = case["question"]
        if question in processed_questions:
            continue

        logger.info(f"[{i+1}/{len(golden_set)}] 검색 수행: {question}")
        
        try:
            response = await runtime_search(question)
            
            # 검색 지표 계산 (정답 ID 매칭)
            t_ids = case.get("target_faq_ids") or ([case.get("target_faq_id")] if case.get("target_faq_id") else [])
            target_ids = set(t_ids)
            ret_ids = [f['faq_id'] for f in response.retrieved_faqs]
            
            found_ids = target_ids.intersection(set(ret_ids))
            
            # 지표 정의
            recall = len(found_ids) / len(target_ids) if target_ids else 0
            precision = len(found_ids) / len(ret_ids) if ret_ids else 0
            
            # MRR (첫 번째 정답이 몇 번째에 나왔나)
            mrr = 0
            for idx, rid in enumerate(ret_ids):
                if rid in target_ids:
                    mrr = 1 / (idx + 1)
                    break

            current_row = {
                "question": question,
                "type": case.get("type", "normal"),
                "target_ids": list(target_ids),
                "retrieved_ids": ret_ids,
                "recall": recall,
                "precision": precision,
                "mrr": mrr,
                "answer": response.answer, # 생성된 답변 (눈으로 확인용)
                "ground_truth": case["ground_truth"]
            }
            rows.append(current_row)
            
            # 즉시 파일 저장
            with open(temp_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(current_row, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.error(f"케이스 {i+1} 오류: {e}")
            continue

    # 3. 최종 결과 통계 및 저장
    if not rows:
        return

    df = pd.DataFrame(rows)
    csv_path = os.path.join(save_dir, "detailed_evaluation_results.csv")
    json_path = os.path.join(save_dir, "summary_metrics.json")
    
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = {
        "overall": {
            "mrr": df["mrr"].mean(),
            "recall": df["recall"].mean(),
            "precision": df["precision"].mean(),
            "total_count": len(df)
        },
        "by_type": df.groupby("type")[["mrr", "recall", "precision"]].mean().to_dict()
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.success(f"평가 완료! {csv_path} 파일을 확인해 보세요.")
    return summary

if __name__ == "__main__":
    GOLDEN_SET_FILE = "evaluate/goldenset.jsonl" 
    asyncio.run(run_evaluation(GOLDEN_SET_FILE))