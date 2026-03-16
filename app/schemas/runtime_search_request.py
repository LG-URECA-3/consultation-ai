from pydantic import BaseModel

class RuntimeSearchRequest(BaseModel):
    question_text: str