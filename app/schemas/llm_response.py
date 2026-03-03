from pydantic import BaseModel, Field

class SummaryResponse(BaseModel):
    summary: str
    keywords: list[str] = Field(default=[])