from sqlmodel import SQLModel
from app.schemas.base.base_consultation_messages import ConsultationMessageBase
from app.schemas.base.base_consultations import ConsultationBase
from app.schemas.consultation_history_es import CustomerPersona
from typing import Optional

class ConsultationHistoryDoc(SQLModel):
    """ES 저장 형식에 따라 작성된 상담 검색 인덱스 스키마"""
    consultation_id: int

    full_text: str # 상담 내용을 모두 연결한 텍스트
    summary_text: str
    summary_vector: list[float]

    # 구조화된 상담 메시지
    messages: list[ConsultationMessageBase]

    keywords: list[str]
    customer_persona: Optional[CustomerPersona] = None

    metadata: ConsultationBase


'''
* 상담 검색 인덱스 형태 예시
{
  "consultation_id": 10023,
  "full_text": "고객: 안녕하세요. 요금제 문의 드립니다.\n상담사: 네, 어떤 점이 궁금하신가요?...",
  "summary_text": "요금제 변경 및 결합 할인 혜택 안내",
  "summary_vector": [0.12, -0.05, 0.88, ...], 
  
  "messages": [
    {
      "sender_type": "CUSTOMER",
      "content": "안녕하세요. 요금제 문의 드립니다.",
      "message_seq": 1
    },
    {
      "sender_type": "AGENT",
      "content": "네, 어떤 점이 궁금하신가요?",
      "message_seq": 2
    }
  ],
  
  "metadata": {
    "customer_id": 101,
    "agent_id": 55,
    "channel_code": "CHAT",
    "product_line_code": "MOBILE",
    "final_result_code": "DONE",
    "started_at": "2026-02-18T14:00:00",
    "ended_at": "2026-02-18T14:15:00"
  }
}
'''