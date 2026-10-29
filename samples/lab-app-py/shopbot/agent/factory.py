"""에이전트 조립. create_agent(model, tools, middleware=[...], context_schema=LabContext, checkpointer).

미들웨어 순서(바깥 → 안): 기록용 TraceRecorder → PII 마스킹(before_model) → 대화 창(wrap_model_call) → 토큰 예산(wrap_model_call)
→ 도구 호출 상한(ToolCallLimitMiddleware 전체 5·도구별 3) → 모델 호출 상한(ModelCallLimitMiddleware).
- 마스킹을 메모리(체크포인터) 앞에 둬야 대화 기록에도 마스킹본만 남는다(11장).
- 창 자르기를 예산 검사 앞에 둬야 예산이 "실제로 보내는" 입력을 본다(8장).
출력 스키마(output_schema 스위치): ProviderStrategy(BotReply) = 모델에 response_format json_schema를 같이 보낸다.
끄면(before) 자유 글 그대로(UNKNOWN으로 감쌈).
대화 메모리: InMemorySaver, thread_id = 로그인 사용자 ID.
"""
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.structured_output import ProviderStrategy
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from labcore.injection import SystemPrompts
from shopbot.agent.middleware import (LabContext, MessageWindowMiddleware, PiiMaskMiddleware, TokenBudgetMiddleware,
                                      TraceRecorderMiddleware)
from shopbot.agent.schemas import BotReply


def build_checkpointer() -> InMemorySaver:
    # 구조화 응답(BotReply·Intent)이 체크포인트에 들어간다. 역직렬화를 허용할 타입을 명시한다
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("shopbot.agent.schemas", "BotReply"),
                                                        ("labcore.injection", "Intent")])
    return InMemorySaver(serde=serde)


def build_chat_agent(lab, model, tools, meter):
    s = lab.settings
    middleware = [TraceRecorderMiddleware()]
    if s.defense.pii_mask:
        middleware.append(PiiMaskMiddleware(lab.masker))
    middleware += [MessageWindowMiddleware(s.memory_max_messages), TokenBudgetMiddleware(meter),
                   ToolCallLimitMiddleware(run_limit=s.tool_calls_total)]
    middleware += [ToolCallLimitMiddleware(tool_name=t.name, run_limit=s.tool_calls_per_tool) for t in tools]
    middleware.append(ModelCallLimitMiddleware(run_limit=s.model_calls_per_run))
    return create_agent(
        model, tools,
        system_prompt=SystemPrompts.AFTER if s.defense.secret_free_prompt else SystemPrompts.BEFORE,
        middleware=middleware,
        response_format=ProviderStrategy(BotReply) if s.defense.output_schema else None,
        context_schema=LabContext,
        checkpointer=lab.checkpointer,
    )
