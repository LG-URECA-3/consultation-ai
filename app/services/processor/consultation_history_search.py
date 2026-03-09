"""요약문 임베딩 기반 consultation_histories 유사도 검색 서비스."""
from __future__ import annotations

from app.core.infrastructure import es_client, openai_client
from app.schemas.consultation_history_es import (
    ConsultationHistorySearchHit,
    ConsultationHistorySearchHitMetadata,
)
from app.services.common import embeddings

CONSULTATION_HISTORIES_INDEX = "consultations_histories"
EMBEDDING_MODEL = "text-embedding-3-small"


async def search_by_summary(
    summary_text: str,
    k: int = 10,
    num_candidates: int = 100,
) -> list[ConsultationHistorySearchHit]:
    """
    요약문을 임베딩한 뒤 consultation_histories 인덱스에서 kNN 유사도 검색.
    """
    if not summary_text.strip():
        return []

    # 1) 요약문 임베딩
    query_vector = await embeddings.get_embedding(summary_text.strip())

    # 2) ES kNN 검색
    resp = await es_client.search(
        index=CONSULTATION_HISTORIES_INDEX,
        knn={
            "field": "summary_vector",
            "query_vector": query_vector,
            "k": k,
            "num_candidates": num_candidates,
        },
        source=["consultation_id", "summary_text", "full_text", "metadata"],
        size=k,
    )

    hits: list[ConsultationHistorySearchHit] = []
    for hit in resp["hits"]["hits"]:
        src = hit.get("_source") or {}
        meta = src.get("metadata") or {}
        hits.append(
            ConsultationHistorySearchHit(
                consultation_id=src.get("consultation_id", ""),
                summary_text=src.get("summary_text", ""),
                full_text=src.get("full_text", ""),
                metadata=ConsultationHistorySearchHitMetadata(
                    agent_id=meta.get("agent_id", ""),
                    customer_id=meta.get("customer_id", ""),
                    category=meta.get("category", ""),
                    resolution_code=meta.get("resolution_code", ""),
                    start_time=meta.get("start_time"),
                    end_time=meta.get("end_time"),
                ),
                score=float(hit.get("_score", 0.0)),
            )
        )

    return hits
