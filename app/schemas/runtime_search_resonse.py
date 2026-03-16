from pydantic import BaseModel
from typing import List, Dict, Any

class RuntimeSearchResponse(BaseModel):
    answer: str
    retrieved_faqs: List[Dict[str, Any]]