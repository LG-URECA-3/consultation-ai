import os
import sys
import asyncio
import pandas as pd
import json
from loguru import logger
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,  # AnswerRelevance -> AnswerRelevancy로 변경됨
    ContextPrecision,
)

current_dir = os.path.dirname(os.path.abspath(__file__)) # evaluate 폴더
root_dir = os.path.abspath(os.path.join(current_dir, "..")) # 상위 루트 폴더
sys.path.append(root_dir)

from datasets import Dataset
from app.services.rumtime.runtime_search import runtime_search
from dotenv import load_dotenv

faithfulness = Faithfulness()
answer_relevancy = AnswerRelevancy()
context_precision = ContextPrecision()

async def run_advanced_evaluation(golden_set_path: str):
    if not os.path.exists(golden_set_path):
        logger.error(f"골든셋 파일을 찾을 수 없습니다: {golden_set_path}")
        return

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = [json.loads(line) for line in f]

    # .env 파일의 환경 변수를 메모리에 로드합니다.
    load_dotenv() 

    # 확인용 (선택 사항): 키가 잘 로드되었는지 체크해볼 수 있습니다.
    if not os.getenv("OPENAI_API_KEY"):
        print("경고: OPENAI_API_KEY가 로드되지 않았습니다. .env 파일을 확인하세요.")

    rows = []
    for i, case in enumerate(golden_set):
        logger.info(f"[{i+1}/{len(golden_set)}] 테스트 중: {case['question']}")
        
        try:
            # 1. 시스템 실행
            response = await runtime_search(case["question"])
            retrieved_ids = [f['faq_id'] for f in response.retrieved_faqs]
            retrieved_contexts = [f['answer'] for f in response.retrieved_faqs]
            
            # 2. 멀티 정답 검색 성능 계산 (Set 기반)
            target_ids_list = case.get("target_faq_ids")
            if target_ids_list is None:
                # 리스트 형태가 없으면 단수형 키를 가져와서 리스트로 만듦
                single_id = case.get("target_faq_id")
                target_ids_list = [single_id] if single_id else []

            target_ids = set(target_ids_list)
            found_ids = set(retrieved_ids)
            
            # 교집합 (얼마나 맞혔나)
            correct_found = target_ids.intersection(found_ids)
            
            # 지표 계산
            recall = len(correct_found) / len(target_ids) if target_ids else 0
            precision = len(correct_found) / len(found_ids) if found_ids else 0
            
            # MRR (여러 개일 경우 가장 먼저 나타난 정답의 순위 기준)
            ranks = [retrieved_ids.index(tid) + 1 for tid in target_ids if tid in retrieved_ids]
            mrr = 1 / min(ranks) if ranks else 0

            rows.append({
                "question": case["question"],
                "type": case.get("type", "normal"),
                "target_ids": list(target_ids),
                "retrieved_ids": retrieved_ids,
                "recall": recall,
                "precision": precision,
                "mrr": mrr,
                "answer": response.answer,
                "contexts": retrieved_contexts,
                "ground_truth": case["ground_truth"]
            })
        except Exception as e:
            logger.error(f"케이스 {i+1} 처리 중 오류 발생: {e}")
            continue

    # 3. RAGAS 평가 (행별 점수 산출)
    logger.info("RAGAS 점수 계산 시작...")
    df = pd.DataFrame(rows)
    ragas_ds = Dataset.from_pandas(df[['question', 'answer', 'contexts', 'ground_truth']])
    ragas_results = evaluate(
        ragas_ds, 
        metrics=[faithfulness, answer_relevancy, context_precision]
    )
    
    # RAGAS 점수를 메인 DF에 합치기
    ragas_scores_df = ragas_results.to_pandas()
    final_df = pd.concat([df, ragas_scores_df.drop(columns=['question', 'answer', 'contexts', 'ground_truth'])], axis=1)

# 1. 저장 경로 설정 (현재 폴더 아래 data/)
    save_dir = "result"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        logger.info(f"'{save_dir}' 폴더가 생성되었습니다.")

    csv_path = os.path.join(save_dir, "detailed_evaluation_results.csv")
    json_path = os.path.join(save_dir, "summary_metrics.json")

    # 4. 결과 저장 (상세 CSV)
    final_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 5. 종합 지표 요약 (JSON)
    summary = {
        "overall": {
            "mrr": final_df["mrr"].mean(),
            "recall": final_df["recall"].mean(),
            "precision": final_df["precision"].mean(),
            "faithfulness": ragas_results["faithfulness"],
            "answer_relevance": ragas_results["answer_relevance"]
        },
        "by_type": final_df.groupby("type")[["mrr", "recall", "precision"]].mean().to_dict()
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.success("평가 완료! CSV와 JSON 요약본이 생성되었습니다.")
    return summary

if __name__ == "__main__":
    # 골든셋 파일 경로를 확인하세요
    GOLDEN_SET_FILE = "evaluate/goldenset.jsonl" 
    
    # 비동기 함수 실행
    asyncio.run(run_advanced_evaluation(GOLDEN_SET_FILE))