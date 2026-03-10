from app.core.infrastructure import openai_client

async def llm_generate_rag_answer(current_question: str, retrieved_faqs: list[dict[str, str]]) -> str:
    """
    유사도가 0.65이상, 0.9 미만인 모든 항목의 질문을 조합하여 하나의 적절한 답변 생성.
    """
    system_prompt = """
        당신은 제공된 FAQ 정보를 바탕으로 상담사의 질문에 가장 적합한 답변을 구성하는 '상담 지원 전문가'입니다. 

        [업무 규정]
        1. 근거 최우선: 오직 아래 제공되는 [참조 FAQ 리스트]의 내용만을 바탕으로 답변을 작성하십시오.
        2. 외부 지식 차단: 당신이 기존에 알고 있는 지식이나 통신사 일반 상식을 절대 추가하지 마십시오.
        3. 답변 불능 시: 제공된 [참조 FAQ 리스트] 내에 [현재 질문]에 대한 직접적인 해답이나 관련 정보가 없다면, 다른 말을 덧붙이지 말고 반드시 "관련된 답변이 없습니다."라고만 출력하십시오.
        4. 문체: 상담사가 고객에게 즉시 안내할 수 있도록 친절하고 명확한 문장으로 작성하십시오.

        [출력 형식]
        - 제공된 정보로 답변이 가능한 경우: {조합된 답변 내용}
        - 제공된 정보로 답변이 불가능한 경우: 관련된 답변이 없습니다.
    """

    faq_context = ""
    for i, faq in enumerate(retrieved_faqs, 1):
        faq_context += f"{i}. 질문: {faq['question']} / 답변: {faq['answer']}\n"

    user_prompt = f"""
        참조 FAQ 리스트: {faq_context}
        현재 질문: {current_question}
    """
    return openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    ).choices[0].message.content.strip()