from pydantic import BaseModel


class ConsultationMessageDetail(BaseModel):
    message_seq: int
    sender_type: str
    content: str


class ConsultationDetailResponse(BaseModel):
    consultation_id: int
    started_at: str | None = None
    ended_at: str | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    phone_mask: str | None = None
    agent_id: int | None = None
    agent_name: str | None = None
    product_line_code: str | None = None
    final_result_code: str | None = None
    summary_text: str | None = None
    customer_request: str | None = None
    agent_action: str | None = None
    messages: list[ConsultationMessageDetail] = []
