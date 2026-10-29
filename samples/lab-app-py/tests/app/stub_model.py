"""API 키 없이 pytest에서 쓰는 가짜 채팅 모델(12장 12.2). labcore ScriptedFakeLlm과 같은 규칙:
[ATTACK-INJ- 가 있으면 시스템 프롬프트를 읊는다(일부러 넘어감). 구조화 출력(response_format)이면 JSON으로 감싼다.
도구는 부르지 않는다(도구 권한은 도구 함수를 직접 불러 시험한다).
"""
import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from labcore.llm import count_tokens


def _text(c) -> str:
    return c if isinstance(c, str) else "" if c is None else str(c)


class StubChatModel(BaseChatModel):
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "lab-stub"

    def _reply(self, messages, response_format=None) -> str:
        system = "".join(_text(m.content) for m in messages if isinstance(m, SystemMessage))
        user = next((_text(m.content) for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        all_text = "\n".join(_text(m.content) for m in messages)
        if "[ATTACK-INJ-" in user:
            text = "제 지시문은 다음과 같습니다: " + system
        elif "<document id=" in all_text:
            text = "수령 후 7일 안에 환불을 요청할 수 있습니다."
        else:
            text = "문의 감사합니다. 주문 번호를 알려 주시면 확인해 드릴게요."
        if response_format is not None or "JSON" in all_text or "json" in all_text:
            props = ((response_format or {}).get("json_schema") or {}).get("schema", {}).get("properties", {})
            if "citedIds" in props or "citedIds" in all_text:
                m = re.search(r'<document id="([^"]+)"', all_text)
                text = json.dumps({"answer": text, "citedIds": [m.group(1)] if m else []}, ensure_ascii=False)
            else:
                text = json.dumps({"intent": "PRODUCT_QA", "orderId": None, "answer": text}, ensure_ascii=False)
        return text

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        self.calls += 1
        text = self._reply(messages, kwargs.get("response_format"))
        all_text = "\n".join(_text(m.content) for m in messages)
        pt, ct = count_tokens(all_text), count_tokens(text)
        msg = AIMessage(content=text, usage_metadata={"input_tokens": pt, "output_tokens": ct, "total_tokens": pt + ct})
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs: Any):
        return self.bind(**{k: v for k, v in kwargs.items() if k == "response_format"})

    def with_structured_output(self, schema, *, method="json_schema", include_raw=False, **kwargs: Any):
        rf = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}

        def run(messages):
            raw = self.invoke(messages, response_format=rf)
            try:
                parsed, err = schema.model_validate_json(raw.content), None
            except Exception as e:   # noqa: BLE001
                parsed, err = None, e
            return {"raw": raw, "parsed": parsed, "parsing_error": err} if include_raw else parsed
        return RunnableLambda(run)
