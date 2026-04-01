from app.core.infrastructure import client, claude_client
from app.schemas.rag_response import RAGResponse
import json
from loguru import logger

async def llm_generate_rag_answer(current_question: str, retrieved_faqs: list[dict[str, str]]) -> str:
    """
    유사도가 0.65이상, 0.9 미만인 모든 항목의 질문을 조합하여 하나의 적절한 답변 생성.
    """
    system_prompt = """
        당신은 제공된 FAQ 데이터를 분석하여 고객의 질문에 가장 적합한 답변을 구성하는 '고객 지원 전문 어시스턴트'입니다.

        [업무 규정]
        1. 근거 최우선: 오직 아래 제공되는 [참조 FAQ 리스트]의 내용만을 바탕으로 답변을 작성하십시오. 최대 15개 중 가장 정확한 내용을 최대 3개만 골라서 답변을 작성하십시오. (무조건 3개를 고를 필요는 없습니다. 일치하는 내용이 3개 미만이면 일치하는 내용만큼만)
        2. 외부 지식 차단: 당신이 기존에 알고 있는 지식이나 외부 상식을 절대 추가하지 마십시오.
        3. 답변 불능 시: 제공된 FAQ 내에 직접적인 해답이나 관련 정보가 없다면, 반드시 "관련된 답변이 없습니다."라고만 답변하십시오.
           (단, 검색된 문서가 질문과 완벽하게 일치하지 않아도 65% 이상 유사한 내용이 있다면 이를 기반으로 최대한 답변을 생성하십시오.)
        4. 식별자 활용: 답변을 위해 선택된 'faq_id'를 반드시 추출하여 리스트에 포함하십시오. 'faq_id'는 최대 3개까지만 포함하십시오.
        5. 답변 내용: 고객의 질문에 대하여 해결 방법이나 정확한 정보를 요약하여 작성하십시오.
        6. 문체: 고객에게 즉시 안내할 수 있도록 친절하고 명확한 문장으로 작성하십시오. (예: ~입니다. ~됩니다. ~합니다. ~십시오.) 절대 마크다운 문법을 사용하지 마십시오.
        7. 답변(answer) 길이: 최대 400자를 넘지 않게 하십시오.

        [출력 규칙]
        - answer: 고객에게 전달할 친절하고 명확한 요약 답변 내용.
        (※ 만약 답변이 불가능한 경우에는 "관련된 답변이 존재하지 않습니다."라고 답변하십시오.)
        - referenced_faq_ids: 답변의 근거가 된 FAQ의 'faq_id' 리스트 (최대 3개). 
        (※ 답변이 불가능한 경우에도 질문과 가장 연관성이 높은 'faq_id'를 최대 3개까지 포함하십시오.)
    """

    # xml 형식으로 추론 능력 향상
    faq_context = json.dumps(retrieved_faqs, ensure_ascii=False, indent=2)
    logger.info(f"LLM 답변 조합 진행: 참조 FAQ 리스트: {faq_context}")
    # user_prompt = f"""
    #     참조 FAQ 리스트: {faq_context}
    #     현재 질문: {current_question}
    # """
    # return client.chat.completions.create(
    #     model="gpt-4o",
    #     response_model=RAGResponse,
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt}],
    #     max_tokens=500,
    # )

    user_prompt = f"""
    <faq_list>
    {faq_context}
    </faq_list>

    <question>
    {current_question}
    </question>
    """
    return claude_client.chat.completions.create(
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
        response_model=RAGResponse,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}],
        max_tokens=500,
        temperature=0.1,
    )