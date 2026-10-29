"""LangChain 미들웨어. 방어 본체는 labcore에 있고, 여기서는 연결만 한다.

before_agent는 한 요청에 한 번, before_model·wrap_model_call은 도구 루프마다 다시 돈다(수업 2-5).
  - 입력 검사: 에이전트 "바깥"의 FastAPI 의존성(web/chat.py guard_input)이 기본이다. InputGuardMiddleware(before_agent)는
    같은 검사를 에이전트 안에 둘 때의 모양(비교용, 기본 조립에는 넣지 않음).
  - PiiMaskMiddleware(before_model): 모델로 보내기 전 사람 메시지를 가린다. 상태(체크포인터)에도 마스킹본만 남는다(11장).
  - MessageWindowMiddleware(wrap_model_call): 최근 N개만 모델에 보낸다(trim_messages, 8장 8.3).
  - TokenBudgetMiddleware(wrap_model_call): 호출 전 예산 확인 → 넘으면 모델을 부르지 않고 429, 호출 뒤 usage_metadata를 장부에(8.2).
  - TraceRecorderMiddleware(wrap_tool_call): 도구 이름·인자·상태(EXECUTED/PROPOSED/DENIED)를 요청 컨텍스트에(eval의 trace.tool_calls).
"""
from dataclasses import dataclass, field

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage, trim_messages

from labcore.audit import RequestIds
from labcore.llm import Usage, count_tokens
from labcore.user import UserContext
from shopbot.web.errors import BudgetExceeded, InputRejected


@dataclass
class LabContext:
    """서버가 넣는 실행 컨텍스트. 모델은 이 값을 보지도 바꾸지도 못한다."""
    user: UserContext
    request_id: str = "req-none"
    trace: list = field(default_factory=list)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return "" if content is None else str(content)


class TokenMeter:
    """예산 확인과 사용량 기록(채팅 미들웨어와 상품 Q&A가 함께 쓴다). 기록은 항상(7.5 "막기 전에 먼저 잰다"), 적용은 스위치."""

    def __init__(self, budget, ledger, enforce: bool, metrics=None):
        self.budget = budget
        self.ledger = ledger
        self.enforce = enforce
        self.metrics = metrics

    def check(self, user: UserContext, texts) -> None:
        if not self.enforce or user is None:
            return
        estimated = sum(count_tokens(t) for t in texts)   # 가짜 규칙(글자 3개 = 1토큰). 실서비스는 모델별 토크나이저로 근사
        d = self.budget.check(user, estimated)
        if not d.allowed:
            raise BudgetExceeded(d.reason, d.user_remaining)

    def record(self, user: UserContext, message) -> None:
        um = getattr(message, "usage_metadata", None) or {}
        u = Usage(int(um.get("input_tokens") or 0), int(um.get("output_tokens") or 0))
        if user is not None:
            self.ledger.add(user.user_id, user.tenant_id, u)
            if self.metrics is not None:
                self.metrics.record_tokens(user.user_id, u)


class InputGuardMiddleware(AgentMiddleware):
    """(비교용) 입력 검사를 before_agent에 둔 모양. 도구 루프마다 다시 돌지 않는다."""

    def __init__(self, guard, suspicious):
        super().__init__()
        self.guard = guard
        self.suspicious = suspicious

    def before_agent(self, state, runtime):
        last = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        text = _text(last.content) if last else None
        r = self.guard.check(text)
        if r.suspicious:
            self.suspicious.record(RequestIds.current(), runtime.context.user.user_id, r.reason, len(text or ""))
        if not r.allowed:
            raise InputRejected(r.reason)
        return None


class PiiMaskMiddleware(AgentMiddleware):
    def __init__(self, masker):
        super().__init__()
        self.masker = masker

    def before_model(self, state, runtime):
        changed = []
        for m in state["messages"]:
            if isinstance(m, HumanMessage):
                masked = self.masker.mask(_text(m.content))
                if masked != _text(m.content):
                    changed.append(HumanMessage(content=masked, id=m.id))   # 같은 id → 상태의 원문을 마스킹본으로 바꾼다
        return {"messages": changed} if changed else None


class MessageWindowMiddleware(AgentMiddleware):
    def __init__(self, max_messages: int):
        super().__init__()
        self.max_messages = max_messages

    def wrap_model_call(self, request, handler):
        if len(request.messages) > self.max_messages:
            trimmed = trim_messages(request.messages, max_tokens=self.max_messages, token_counter=len,
                                    strategy="last", start_on="human", allow_partial=False)
            request = request.override(messages=trimmed)
        return handler(request)


class TokenBudgetMiddleware(AgentMiddleware):
    def __init__(self, meter: TokenMeter):
        super().__init__()
        self.meter = meter

    def wrap_model_call(self, request, handler):
        user = getattr(request.runtime.context, "user", None)
        texts = ([_text(request.system_message.content)] if request.system_message else []) + \
                [_text(m.content) for m in request.messages]
        self.meter.check(user, texts)
        response = handler(request)
        for m in getattr(response, "result", None) or [response]:
            if getattr(m, "usage_metadata", None):
                self.meter.record(user, m)
        return response


class TraceRecorderMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        result = handler(request)
        art = getattr(result, "artifact", None) if isinstance(result, ToolMessage) else None
        name = request.tool_call.get("name")
        if isinstance(art, dict) and "status" in art:
            args, status = art.get("arguments") or {}, art["status"]
        else:   # 인자 검증 실패 등 도구가 돌지 않은 경우
            args, status = {k: "null" if v is None else str(v) for k, v in (request.tool_call.get("args") or {}).items()}, "DENIED"
        ctx = request.runtime.context
        if ctx is not None:
            ctx.trace.append({"name": name, "arguments": args, "status": status})
        return result
