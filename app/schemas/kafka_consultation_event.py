from pydantic import BaseModel
from pydantic import Field

class ConsultationEvent(BaseModel):
    record_id: int = Field(alias="recordId")
    consultation_id: int = Field(alias="consultationId")
    completed_at: str = Field(alias="completedAt")