# 요약만 임베딩을 위한 함수
from app.core.infrastructure import openai_client, client
from app.schemas.llm_response import SummaryResponse
from app.core.config import settings


async def get_embedding(text: str) -> list[float]:
    """OPENAI 임베딩 생성 함수"""
    return openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
        dimensions=settings.EMBEDDING_DIMS
    ).data[0].embedding


# 임시 텍스트 요약(OpenAI 호출) 함수 (나중에 삭제 예정)
async def get_summary_text(text: str) -> SummaryResponse:
    """임시 텍스트 요약(OpenAI 호출) 함수"""
    system_prompt = """
        당신은 통신사 상담 내역을 분석하여 FAQ 데이터베이스와의 유사도를 측정하기 위한 '표준 요약문' 생성 전문가입니다. 상담 원문이 주어지면, 아래 가이드라인에 따라 검색 효율이 가장 높은 형태의 요약문을 생성하세요. 

        [요약 가이드라인] 
        1. 용어 표준화: 고객의 비정형 표현을 통신 전문 용어로 변환하십시오. 
        2. 핵심 구조: [서비스/대상] [현상/문제] [사용자 의도]의 구조로 단문을 작성하십시오. 
        3. 노이즈 제거: 상담원의 인사말, 공감 멘트, 사적인 대화는 모두 제외하고 '고객의 목적'에만 집중하십시오. 
        4. 문체: '~함', '~함에 따른 ~요청'과 같은 명사형 구문으로 마칩니다. 
        5. FAQ 최적화: 유사한 상황의 다른 상담과 비교했을 때 '동일한 질문'으로 분류될 수 있도록 일반화하여 작성하십시오. 

        [출력 형식] - Summary: {표준 요약문} - Keywords: {쉼표로 구분된 핵심 키워드 3~5개}
    """
    return client.chat.completions.create(
        model="gpt-4o",
        response_model=SummaryResponse,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
