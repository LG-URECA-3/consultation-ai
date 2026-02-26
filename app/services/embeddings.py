# 요약만 임베딩을 위한 함수
from app.core.infrastructure import openai_client


async def get_embedding(text: str) -> list[float]:
    """OPENAI 임베딩 생성 함수"""
    return openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
        dimensions=512
    ).data[0].embedding


# 임시 텍스트 요약(OpenAI 호출) 함수 (나중에 삭제 예정)
async def get_summary_text(text: str) -> str:
    """임시 텍스트 요약(OpenAI 호출) 함수"""
    return openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes consultation context for search."},
            {"role": "user", "content": text}
        ]
    ).choices[0].message.content
