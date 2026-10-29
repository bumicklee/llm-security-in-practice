"""11장 출력·개인정보·보관 기간."""
import hashlib
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


class PiiMasker:
    """모델로 보내기 전·저장하기 전 개인정보·비밀 가리기(11장 11.2, 11.5).

    휴대폰 010-1234-5678 → 010-****-5678 / 이메일 alice@example.com → a****@example.com / 키 sk-test-FAKE-0000 → sk-****
    정규식 마스킹은 놓치는 것이 있다. "모델에 꼭 보내야 하나?"를 먼저 묻는다.
    LangChain PIIMiddleware 기본 탐지기에는 한국 휴대폰 모양이 없어서 이 규칙을 직접 둔다(탐지기 목록 확인 필요).
    """
    _PHONE = re.compile(r"(01[016789])[-\s]?([0-9]{3,4})[-\s]?([0-9]{4})")
    _EMAIL = re.compile(r"([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    _KEY = re.compile(r"sk-[A-Za-z0-9_-]{6,}")

    def mask(self, s: str | None) -> str | None:
        if s is None:
            return None
        r = self._PHONE.sub(r"\1-****-\3", s)
        r = self._EMAIL.sub(r"\1****@\2", r)
        return self._KEY.sub("sk-****", r)


class HtmlOutputEscaper:
    """LLM 답은 사용자 입력처럼 다룬다(11장 11.1). 화면에 넣기 전에 HTML 이스케이프.
    브라우저 쪽은 innerHTML 대신 textContent(shopbot/static/app.js)."""
    _TABLE = str.maketrans({"<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;"})
    _BOLD = re.compile(r"\*\*([^*<>]{1,100})\*\*")

    @classmethod
    def escape(cls, s: str | None) -> str:
        return "" if s is None else s.translate(cls._TABLE)

    @classmethod
    def render_limited_markdown(cls, s: str | None) -> str:
        """허용 목록 마크다운: **굵게**와 줄바꿈만. 이스케이프를 먼저 한 뒤에 바꾼다."""
        return cls._BOLD.sub(r"<strong>\1</strong>", cls.escape(s)).replace("\n", "<br>")


class ReplyRenderer:
    """답을 HTML 조각으로 바꾸는 곳. 수정 전 RAW / 수정 후 ESCAPED."""

    def __init__(self, fn: Callable[[str], str]):
        self._fn = fn

    def to_html(self, model_text: str) -> str:
        return self._fn(model_text)


ReplyRenderer.RAW = ReplyRenderer(lambda t: '<div class="bot">' + t + "</div>")  # [수정 전]
ReplyRenderer.ESCAPED = ReplyRenderer(
    lambda t: '<div class="bot">' + HtmlOutputEscaper.render_limited_markdown(t) + "</div>")  # [수정 후]


class PromptLogPolicy:
    """로그에 프롬프트 원문을 남기지 않는다(11장 11.5).

    raw(수정 전): 원문 그대로 / safe(수정 후): 해시 앞 12자리 + 길이 + 마스킹본 앞 80자
    LangChain set_debug(True)·트레이싱 환경 변수는 원문을 밖으로 보낸다 → shopbot이 시작할 때 막는다.
    """

    @staticmethod
    def raw(prompt: str) -> str:
        return "prompt=" + prompt

    @staticmethod
    def safe(prompt: str, masker: PiiMasker) -> str:
        masked = masker.mask(prompt)
        head = masked[:80] + "…" if len(masked) > 80 else masked
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return f'promptSha256={digest[:12]} len={len(prompt)} masked="{head}"'


@dataclass(frozen=True)
class Turn:
    user_id: str
    at: datetime
    masked_text: str


class ConversationStore:
    """대화 기록 보관 기간(11장 11.3). 저장할 때 마스킹본만, 기간이 지나면 지운다(배치가 purge 호출)."""

    def __init__(self, clock: Callable[[], datetime], masker: PiiMasker):
        self._clock = clock
        self._masker = masker
        self._turns: list[Turn] = []
        self._lock = threading.Lock()

    def save(self, user_id: str, text: str) -> None:
        with self._lock:
            self._turns.append(Turn(user_id, self._clock(), self._masker.mask(text)))

    def purge_older_than(self, retention: timedelta) -> int:
        cut = self._clock() - retention
        with self._lock:
            before = len(self._turns)
            self._turns = [t for t in self._turns if not t.at < cut]
            return before - len(self._turns)

    def all(self) -> list[Turn]:
        with self._lock:
            return list(self._turns)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
