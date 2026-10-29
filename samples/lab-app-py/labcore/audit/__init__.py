"""요청 ID 하나로 질문·검색 문서·도구 호출·승인을 잇는 감사 로그(11장 11.4).

원문 프롬프트 대신 마스킹본·해시·길이를 남긴다(11.5). 요청 ID는 contextvars로 넘긴다
(FastAPI는 요청마다 다른 스레드·태스크에서 돌기 때문에 전역 변수가 아니라 contextvars가 맞다).
"""
import contextvars
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

_CURRENT: contextvars.ContextVar[str | None] = contextvars.ContextVar("lab_request_id", default=None)


class RequestIds:
    """요청 ID 보관. shopbot은 요청 ID 미들웨어에서 begin/end를 부른다."""
    _tokens: dict = {}

    @staticmethod
    def begin() -> str:
        rid = "req-" + str(uuid.uuid4())[:8]
        _CURRENT.set(rid)
        return rid

    @staticmethod
    def set(rid: str) -> contextvars.Token:
        return _CURRENT.set(rid)

    @staticmethod
    def current() -> str:
        rid = _CURRENT.get()
        return "req-none" if rid is None else rid

    @staticmethod
    def end() -> None:
        _CURRENT.set(None)


@dataclass(frozen=True)
class Event:
    request_id: str
    at: datetime
    type: str
    actor: str
    detail: str

    def to_json(self) -> dict:
        at = self.at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"requestId": self.request_id, "at": at, "type": self.type, "actor": self.actor, "detail": self.detail}


class AuditLog:
    def __init__(self, sink=None):
        """sink: 이벤트마다 JSON 한 줄을 받는 함수(선택). shopbot은 표준 로그로 JSON 줄을 낸다(11장)."""
        self._events: list[Event] = []
        self._lock = threading.Lock()
        self._sink = sink

    def question(self, actor, masked_text): self._add("QUESTION", actor, masked_text)
    def retrieved(self, actor, doc_ids): self._add("RETRIEVED", actor, doc_ids)
    def tool_call(self, actor, tool, args): self._add("TOOL_CALL", actor, f"{tool} {args}")
    def denied(self, actor, tool, why): self._add("TOOL_DENIED", actor, f"{tool} {why}")
    def proposed(self, actor, tool, detail): self._add("PROPOSED", actor, f"{tool} {detail}")
    def approved(self, actor, tool, detail): self._add("APPROVED", actor, f"{tool} {detail}")
    def rejected(self, actor, tool, detail): self._add("REJECTED", actor, f"{tool} {detail}")
    def answer(self, actor, masked_text): self._add("ANSWER", actor, masked_text)

    def _add(self, type_: str, actor: str, detail: str) -> None:
        e = Event(RequestIds.current(), datetime.now(timezone.utc), type_, actor, detail)
        with self._lock:
            self._events.append(e)
        if self._sink is not None:
            self._sink(json.dumps(e.to_json(), ensure_ascii=False))

    def by_request_id(self, request_id: str) -> list[Event]:
        with self._lock:
            return [e for e in self._events if e.request_id == request_id]

    def all(self) -> list[Event]:
        with self._lock:
            return list(self._events)
