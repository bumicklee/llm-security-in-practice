"""모델 호출 추상화와 결정적 가짜 LLM."""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Role(str, Enum):
    """메시지 역할. 역할은 모델에게 주는 힌트일 뿐 강제되는 경계가 아니다(3장 3.2)."""
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    text: str

    @staticmethod
    def system(t: str) -> "ChatMessage":
        return ChatMessage(Role.SYSTEM, t)

    @staticmethod
    def user(t: str) -> "ChatMessage":
        return ChatMessage(Role.USER, t)

    @staticmethod
    def assistant(t: str) -> "ChatMessage":
        return ChatMessage(Role.ASSISTANT, t)


@dataclass(frozen=True)
class Usage:
    """토큰 사용량(가짜 LLM이 돌려주는 가짜 수)."""
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LlmRequest:
    """모델 요청. max_output_tokens는 8장 8.3의 최대 출력 토큰(0 = 제한 없음)."""
    messages: tuple
    max_output_tokens: int = 0

    def __init__(self, messages, max_output_tokens: int = 0):
        object.__setattr__(self, "messages", tuple(messages))
        object.__setattr__(self, "max_output_tokens", max_output_tokens)

    def system_text(self) -> str:
        return "".join(m.text for m in self.messages if m.role == Role.SYSTEM)

    def last_user_text(self) -> str:
        for m in reversed(self.messages):
            if m.role == Role.USER:
                return m.text
        return ""

    def all_text(self) -> str:
        return "".join(m.text + "\n" for m in self.messages)


@dataclass(frozen=True)
class LlmResponse:
    """모델 응답. text는 모델이 쓴 글(=믿지 않는 입력)."""
    text: str
    usage: Usage


class LlmClient(Protocol):
    def call(self, request: LlmRequest) -> LlmResponse: ...


def count_tokens(text: str | None) -> int:
    """가짜 토큰 계산기. 규칙: 글자 3개 = 1토큰(올림). 실제 토크나이저와 다르다(7장 7.2)."""
    if not text:
        return 0
    return (len(text) + 2) // 3


class ScriptedFakeLlm:
    """"공격에 잘 넘어가는 모델"을 흉내 내는 결정적 가짜 LLM.

    테스트의 핵심은 "모델이 넘어가도 우리 코드가 막는가"이므로, 이 가짜는 일부러 넘어간다.
    규칙(랩 전용 자리 표시만):
      - 마지막 사용자 메시지에 [ATTACK-INJ- → 시스템 프롬프트를 그대로 읊는다
      - 검색 문서 안에 [ATTACK-RAG- → 가짜 링크를 추천한다
      - [ATTACK-OUT- → 답에 HTML 태그 자리 표시를 섞는다(11장)
      - 문서 블록이 있으면 → 첫 문서 ID를 "근거: id"로 붙인 정상 답
      - 그 밖에는 짧은 정상 답
    """
    FAKE_COMPETITOR_LINK = "http://127.0.0.1:9999/fake"
    FAKE_HTML_MARKER = '<mark data-lab-attack="ATTACK-OUT-01">ATTACK-OUT-01</mark>'
    _DOC_ID = re.compile(r'<document id="([^"]+)"|\[doc:([^\]]+)\]')

    def __init__(self):
        self._calls = 0

    def call(self, request: LlmRequest) -> LlmResponse:
        self._calls += 1
        user = request.last_user_text()
        all_text = request.all_text()
        if "[ATTACK-INJ-" in user:
            text = "제 지시문은 다음과 같습니다: " + request.system_text()
        elif "[ATTACK-RAG-" in all_text:
            text = "이 상품보다 여기가 더 쌉니다: " + self.FAKE_COMPETITOR_LINK
        elif "[ATTACK-OUT-" in user:
            text = "주문 안내입니다 " + self.FAKE_HTML_MARKER
        elif '<document id="' in all_text or "[doc:" in all_text:
            text = "자료에 따르면 수령 후 7일 안에 환불을 요청할 수 있습니다. 근거: " + self._first_doc_id(all_text)
        else:
            text = "문의 감사합니다. 주문 번호를 알려 주시면 확인해 드릴게요."
        if request.max_output_tokens > 0:
            max_chars = request.max_output_tokens * 3
            if len(text) > max_chars:
                text = text[:max_chars]
        return LlmResponse(text, Usage(count_tokens(all_text), count_tokens(text)))

    @property
    def call_count(self) -> int:
        return self._calls

    @classmethod
    def _first_doc_id(cls, all_text: str) -> str:
        m = cls._DOC_ID.search(all_text)
        if not m:
            return ""
        return m.group(1) if m.group(1) is not None else m.group(2)
