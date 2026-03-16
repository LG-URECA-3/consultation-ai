from pydantic import BaseModel, Field

class SummaryKeywordResponse(BaseModel):
    summary: str
    keywords: list[str] = Field(default=[])