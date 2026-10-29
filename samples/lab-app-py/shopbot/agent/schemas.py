"""HTTP 응답·구조화 출력 스키마. 필드 이름은 HTTP 계약의 camelCase."""
from pydantic import BaseModel, Field

from labcore.injection import Intent


class BotReply(BaseModel):
    """상담봇 답의 고정된 모양(4장 4.4). 모델 출력은 이 스키마(json_schema)로만 받고, 형식이 틀리면 정해진 거절 답."""
    intent: Intent | None = Field(None, description="ORDER_STATUS | CANCEL_REQUEST | PRODUCT_QA | UNKNOWN")
    orderId: str | None = Field(None, description="주문 번호(숫자 4~10자리) 또는 null")
    answer: str | None = Field(None, description="고객에게 보여 줄 답")


class ToolCallTrace(BaseModel):
    name: str
    arguments: dict
    status: str   # EXECUTED | PROPOSED | DENIED


class Trace(BaseModel):
    request_id: str
    tool_calls: list[ToolCallTrace]


class EvalBotReply(BotReply):
    """eval 프로필에서만: 응답에 trace를 붙인다. 기본 응답 모양은 바뀌지 않는다."""
    trace: Trace


class GroundedAnswer(BaseModel):
    """근거 문서 ID가 붙은 답(5장 5.5)."""
    answer: str = Field(description="답")
    citedIds: list[str] = Field(default_factory=list, description="근거로 쓴 문서 id 목록")


class ChatRequest(BaseModel):
    # 길이 상한은 넉넉하게: 짧은 max_length를 두면 Pydantic이 422를 낸다(입력 가드의 400 INPUT_REJECTED와 달라진다).
    # 검사는 입력 가드(web/chat.py guard_input)가 한다(4.2).
    message: str | None = Field(None, max_length=200_000)


class AskRequest(BaseModel):
    question: str | None = Field(None, max_length=200_000)


class ReviewRequest(BaseModel):
    text: str | None = Field(None, max_length=200_000)


class FixtureRequest(BaseModel):
    enabled: bool | None = None
