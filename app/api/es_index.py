from fastapi import APIRouter, HTTPException
from loguru import logger
from app.services.save_es_index import save_consultation_index

router = APIRouter(prefix="/consultations", tags=["ES Index"])


@router.post("/{consultation_id}/index")
async def index_consultation(consultation_id: int):
    """상담 데이터를 Elasticsearch에 인덱싱합니다."""
    try:
        result = await save_consultation_index(consultation_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"consultation_id={consultation_id} 데이터를 찾을 수 없거나 인덱싱에 실패했습니다.")
        
        logger.info(f"인덱싱 완료: consultation_id={consultation_id}")
        return {
            "message": "인덱싱이 완료되었습니다.",
            "consultation_id": consultation_id,
            "es_result": dict(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"인덱싱 중 오류 발생: consultation_id={consultation_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"인덱싱 중 오류가 발생했습니다: {str(e)}")
