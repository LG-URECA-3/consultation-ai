from app.schemas.base.base_consultation_messages import ConsultationMessageBase

def get_full_text(messages: list[ConsultationMessageBase]) -> str:
    """상담 메시지를 모두 연결한 전체 텍스트 생성 함수"""
    return "\n".join([f"{message.sender_type.value}: {message.content}" for message in messages])