"""상담 채팅 API. POST /api/chat {"message": "..."} → BotReply {intent, orderId, answer}

- 사용자 정보는 로그인(HTTP Basic)에서. 모델 인자·채팅 내용에서 꺼내지 않는다. 도구에는 ToolRuntime 컨텍스트로 넘긴다(9.3).
- 의존성 순서: 로그인 → 레이트 리밋(8.1) → 입력 가드(4.2, 에이전트 "바깥"). 가드에 걸리면 모델을 부르지 않는다(토큰 0).
- 출력 스키마(4.4): 구조화 출력(json_schema) → ReplyPolicy로 한 번 더 검사. 형식이 틀리면 정해진 거절 답.
"""
from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, HumanMessage

from labcore.audit import RequestIds
from labcore.injection import BotReply as CoreBotReply
from labcore.injection import Intent
from shopbot.agent.middleware import LabContext
from shopbot.agent.schemas import BotReply, ChatRequest, EvalBotReply
from shopbot.state import LabState, get_chat_model, get_lab
from shopbot.web.errors import BudgetExceeded, InputRejected
from shopbot.web.rate_limit import rate_limited_user


def guard_input(req: ChatRequest, user=Depends(rate_limited_user), lab: LabState = Depends(get_lab)):
    """입력 경계 검사(4장 4.2). 길이·문자·형식만 본다. 의심 입력은 원문 없이 기록한다(4.5)."""
    if lab.settings.defense.input_guard:
        r = lab.input_guard.check(req.message)
        if r.suspicious:
            lab.suspicious.record(RequestIds.current(), user.user_id, r.reason, len(req.message or ""))
        if not r.allowed:
            raise InputRejected(r.reason)
    return user


def _last_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not m.tool_calls:
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def run_chat(lab: LabState, agent, user, message: str) -> tuple[CoreBotReply, list]:
    ctx = LabContext(user=user, request_id=RequestIds.current())
    config = {"configurable": {"thread_id": user.user_id}}
    inputs = {"messages": [HumanMessage(message)]}
    if lab.settings.defense.output_schema:
        try:
            out = agent.invoke(inputs, config=config, context=ctx)
            sr = out.get("structured_response")
            raw = CoreBotReply(sr.intent, sr.orderId, sr.answer) if sr is not None else CoreBotReply.refusal()
        except (InputRejected, BudgetExceeded):
            raise                       # 방어가 막은 것은 400/429로 그대로 내보낸다
        except Exception:               # 스키마 변환 실패·모델 오류 = 정해진 문구
            raw = CoreBotReply.refusal()
        reply = lab.reply_policy.enforce(raw)
    else:
        out = agent.invoke(inputs, config=config, context=ctx)
        reply = CoreBotReply(Intent.UNKNOWN, None, _last_text(out["messages"]))   # [수정 전] 자유 글 그대로
    return reply, ctx.trace


def build_router(eval_enabled: bool) -> APIRouter:
    router = APIRouter()
    model = EvalBotReply if eval_enabled else BotReply

    @router.post("/api/chat", response_model=model)
    def chat(req: ChatRequest, user=Depends(guard_input), lab: LabState = Depends(get_lab), model=Depends(get_chat_model)):
        lab.audit.question(user.user_id, lab.masker.mask(str(req.message)))
        reply, trace = run_chat(lab, lab.agent_for(model), user, req.message)
        lab.audit.answer(user.user_id, lab.masker.mask(reply.answer))
        body = {"intent": reply.intent, "orderId": reply.order_id, "answer": reply.answer}
        if eval_enabled:
            body["trace"] = {"request_id": RequestIds.current(), "tool_calls": trace}
        return body

    return router
