"""요약문 임베딩 기반 consultation_histories 유사도 검색 서비스."""
from __future__ import annotations

from app.core.infrastructure import es_client, openai_client
from app.schemas.consultation_history_es import (
    ConsultationHistorySearchHit,
    ConsultationHistorySearchHitMetadata,
    ConsultationSearchRequest,
    ConsultationSearchHit,
    ConsultationSearchResponse,
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


async def search_consultations_list(req: ConsultationSearchRequest) -> ConsultationSearchResponse:
    """
    키워드 + 필터 기반 상담 이력 목록 검색.
    - keyword: summary_text / full_text multi_match 또는 consultation_id 숫자 일치
    - agent_id, date_from/to, final_result_code 필터
    - 페이지네이션
    """
    must: list[dict] = []
    filter_clauses: list[dict] = []

    if req.keyword and req.keyword.strip():
        kw = req.keyword.strip()
        if kw.lstrip("#").isdigit():
            filter_clauses.append({"term": {"consultation_id": int(kw.lstrip("#"))}})
        else:
            must.append({
                "multi_match": {
                    "query": kw,
                    "fields": ["summary_text", "full_text", "metadata.customer_name"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })

    if req.agent_id is not None:
        filter_clauses.append({"term": {"metadata.agent_id": req.agent_id}})

    if req.date_from or req.date_to:
        range_clause: dict = {}
        if req.date_from:
            range_clause["gte"] = req.date_from
        if req.date_to:
            range_clause["lte"] = req.date_to
        filter_clauses.append({"range": {"metadata.ended_at": range_clause}})

    if req.final_result_code:
        filter_clauses.append({"term": {"metadata.final_result_code": req.final_result_code}})

    if must or filter_clauses:
        query: dict = {"bool": {}}
        if must:
            query["bool"]["must"] = must
        if filter_clauses:
            query["bool"]["filter"] = filter_clauses
    else:
        query = {"match_all": {}}

    from_idx = (req.page - 1) * req.size

    resp = await es_client.search(
        index=CONSULTATION_HISTORIES_INDEX,
        query=query,
        source=["consultation_id", "summary_text", "metadata"],
        from_=from_idx,
        size=req.size,
        sort=[{"metadata.ended_at": {"order": "desc", "missing": "_last"}}],
    )

    hits: list[ConsultationSearchHit] = []
    for hit in resp["hits"]["hits"]:
        src = hit.get("_source") or {}
        meta = src.get("metadata") or {}
        hits.append(ConsultationSearchHit(
            consultation_id=src.get("consultation_id", 0),
            summary_text=src.get("summary_text", ""),
            customer_id=meta.get("customer_id"),
            customer_name=meta.get("customer_name"),
            agent_id=meta.get("agent_id"),
            agent_name=meta.get("agent_name"),
            product_line_code=meta.get("product_line_code"),
            final_result_code=meta.get("final_result_code"),
            started_at=str(meta["started_at"]) if meta.get("started_at") else None,
            ended_at=str(meta["ended_at"]) if meta.get("ended_at") else None,
        ))

    total_raw = resp["hits"]["total"]
    total = total_raw["value"] if isinstance(total_raw, dict) else int(total_raw)

    return ConsultationSearchResponse(hits=hits, total=total, page=req.page, size=req.size)
