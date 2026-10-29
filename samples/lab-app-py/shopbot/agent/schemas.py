"""HTTP 응답·구조화 출력 스키마. 필드 이름은 HTTP 계약의 camelCase."""
import json

from pydantic import BaseModel, Field, ValidationError

from labcore.injection import Intent


class BotReply(BaseModel):
    """상담봇 답의 고정된 모양(4장 4.4). 모델 출력은 이 스키마로만 받고(provider = json_schema, tool = 답 제출 도구 호출),
    형식이 틀리면 정해진 거절 답."""
    intent: Intent | None = Field(None, description="ORDER_STATUS | CANCEL_REQUEST | PRODUCT_QA | UNKNOWN")
    orderId: str | None = Field(None, description="주문 번호(숫자 4~10자리) 또는 null")
    answer: str | None = Field(None, description="고객에게 보여 줄 답")


REPLY_KEYS = frozenset({"intent", "orderId", "answer"})


def reply_from_text(text: str) -> BotReply | None:
    """structured_output: tool(lmstudio)에서 모델이 "답 제출" 도구 대신 글로 낸 답을 받는 마지막 길(2026-10-29 실측).
    gpt-oss가 LM Studio에서 `<|channel|>final <|constrain|>json<|message|>{...}`처럼 내부 표시를 붙여 내는 경우가 있다.
    글 안의 JSON 객체 하나가 정확히 답 모양(키 intent·orderId·answer만, answer는 글자)일 때만 받는다.
    그 밖(도구 호출 흉내 `{"name": …}`, 속생각 `{"analysis": …}`, 깨진 JSON)은 None → 호출한 쪽이 정해진 거절 답을 낸다."""
    if not isinstance(text, str) or "{" not in text or "}" not in text:
        return None
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) - REPLY_KEYS or not isinstance(data.get("answer"), str):
        return None
    try:
        return BotReply.model_validate(data)
    except ValidationError:
        return None


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
