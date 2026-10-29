"""5~6장 RAG 방어 부품과 수정 전/후 쌍."""
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol
from urllib.parse import urlsplit

from labcore.injection import SystemPrompts
from labcore.llm import ChatMessage, LlmRequest
from labcore.user import UserContext


class Visibility(str, Enum):
    """문서 공개 범위(6장 표 6-1). INTERNAL은 같은 테넌트 직원(UserContext.staff)만."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class TrustLevel(str, Enum):
    """문서 신뢰 등급(5장 표 5-1). 고객 작성 문서는 가장 낮다."""
    OFFICIAL = "OFFICIAL"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


@dataclass(frozen=True)
class KnowledgeDoc:
    """벡터 저장소에 넣는 문서 한 개와 권한·출처 메타데이터. tenantId/visibility → 6장, source/trust → 5장."""
    id: str
    tenant_id: str
    visibility: Visibility
    source: str
    trust: TrustLevel
    text: str


@dataclass(frozen=True)
class ScanFinding:
    """수집 검사기 발견 사항(노란 경고 배지)."""
    doc_id: str
    kind: str
    detail: str

    def to_json(self) -> dict:
        return {"docId": self.doc_id, "kind": self.kind, "detail": self.detail}


NO_GROUND = "확인할 수 없습니다"


@dataclass(frozen=True)
class GroundedAnswer:
    """근거 문서 ID가 붙은 답(5장 5.5)."""
    answer: str
    cited_ids: tuple = ()

    def __init__(self, answer: str, cited_ids=None):
        object.__setattr__(self, "answer", answer)
        object.__setattr__(self, "cited_ids", tuple(cited_ids or ()))

    @staticmethod
    def no_ground() -> "GroundedAnswer":
        return GroundedAnswer(NO_GROUND, ())


_URL = re.compile(r"https?://[^\s\"'<>)]+")


def _host_of(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class DocumentFencer:
    """검색된 문서를 프롬프트 안에서 "데이터 블록"으로 감싼다(5장 5.4).

    본문 속 < > & " 는 이스케이프해 블록을 닫거나 새 블록을 여는 흉내를 못 하게 한다.
    감싸기는 경계를 "강제"하지 못한다. 그래서 GroundingPolicy와 함께 쓴다.
    """

    @staticmethod
    def fence(docs) -> str:
        out = []
        for d in docs:
            out.append(f'<document id="{_esc(d.id)}" source="{_esc(d.source)}" trust="{d.trust.value}">\n'
                       f"{_esc(d.text)}\n</document>\n")
        return "".join(out)


class FilterValues:
    """필터 "문자열"에 값을 이어 붙이는 위험(6장 6.3)을 보여 주는 전후 쌍.

    unsafe_concat: "tenantId == '" + value + "'" → 따옴표 하나로 식의 구조가 바뀐다
    require_safe_tenant: 로그인 정보의 값이라도 형식을 검사한다. 가능하면 문자열 대신 콜러블 필터(방법 A)를 쓴다.
    """
    _TENANT = re.compile(r"[a-z0-9-]{1,32}")

    @staticmethod
    def unsafe_concat(value: str) -> str:
        return "tenantId == '" + value + "'"

    @classmethod
    def require_safe_tenant(cls, value: str | None) -> str:
        if value is None or not cls._TENANT.fullmatch(value):
            raise ValueError("허용되지 않은 테넌트 값")
        return value


class GroundingPolicy:
    """근거 없는 답·허용 밖 링크가 든 답을 내보내지 않는다(5장 5.5)."""

    def __init__(self, allowed_link_hosts):
        self.allowed = frozenset(allowed_link_hosts)

    def enforce(self, a: GroundedAnswer | None, retrieved) -> GroundedAnswer:
        if a is None or not a.cited_ids:
            return GroundedAnswer.no_ground()
        ids = {d.id for d in retrieved}
        if not set(a.cited_ids) <= ids:
            return GroundedAnswer.no_ground()
        for m in _URL.finditer(a.answer):
            host = _host_of(m.group())
            if host is None or host not in self.allowed:
                return GroundedAnswer.no_ground()
        return a


class IngestionScanner:
    """문서를 벡터 저장소에 넣기 "전에" 지시처럼 보이는 흔적을 표시한다(5장 5.3). 기본은 사람 검토 목록으로.

    보이지 않는 문자·HTML 주석·숨김 / 역할 표시·블록 닫는 태그 흉내 / 허용 목록 밖 링크 / 랩 표지 [ATTACK-RAG-xx]
    """
    _HIDDEN = re.compile(r"[​-‏⁠﻿]|<!--|display\s*:\s*none")
    _ROLE = re.compile(r"^\s*(system|assistant|developer)\s*[:：]|</\s*document", re.IGNORECASE | re.MULTILINE)
    _LAB_MARK = re.compile(r"\[ATTACK-RAG-[0-9]+")

    def __init__(self, allowed_link_hosts):
        self.allowed = frozenset(allowed_link_hosts)

    def scan(self, doc: KnowledgeDoc) -> list[ScanFinding]:
        out = []
        t = doc.text
        if self._HIDDEN.search(t):
            out.append(ScanFinding(doc.id, "HIDDEN_TEXT", "보이지 않는 글자 또는 숨김 표시"))
        if self._ROLE.search(t):
            out.append(ScanFinding(doc.id, "ROLE_SPOOF", "역할 표시·블록 태그 흉내"))
        for m in _URL.finditer(t):
            host = _host_of(m.group())
            if host is None or host not in self.allowed:
                out.append(ScanFinding(doc.id, "UNKNOWN_LINK", str(host)))
        if self._LAB_MARK.search(t):
            out.append(ScanFinding(doc.id, "LAB_ATTACK_MARK", "랩 공격 표지"))
        return out


_WORD_SPLIT = re.compile(r"[\W_]+")


def words(s: str) -> set[str]:
    """글자·숫자가 아닌 곳에서 자른 덩어리 중 두 글자 이상."""
    return {w for w in _WORD_SPLIT.split(s.lower()) if len(w) >= 2}


class KnowledgeStore:
    """장난감 "벡터 저장소". 실제 임베딩 대신 단어 겹침 수로 비슷함을 잰다.
    핵심은 실제와 같다: 비슷한 문서를 찾을 뿐, 볼 권한은 묻지 않는다(6장 6.2)."""

    def __init__(self):
        self._docs: list[KnowledgeDoc] = []
        self._lock = threading.Lock()

    def add(self, d: KnowledgeDoc) -> None:
        with self._lock:
            self._docs.append(d)

    def search(self, query: str, top_k: int, flt: Callable[[KnowledgeDoc], bool]) -> list[KnowledgeDoc]:
        q = words(query)
        with self._lock:
            docs = list(self._docs)
        scored = [(d, len(q & words(d.text))) for d in docs if flt(d)]
        hits = [x for x in scored if x[1] > 0]
        hits.sort(key=lambda x: -x[1])  # 안정 정렬(같은 점수는 넣은 순서)
        return [d for d, _ in hits[:top_k]]

    @staticmethod
    def seed_docs() -> list[KnowledgeDoc]:
        """랩 시드 데이터: shop-a / shop-b 문서와 고객 리뷰(가짜)."""
        return [
            KnowledgeDoc("manual-7", "shop-a", Visibility.PUBLIC, "manual", TrustLevel.OFFICIAL,
                         "환불 규정: 수령 후 7일 안에 환불을 요청할 수 있습니다."),
            KnowledgeDoc("policy-a-int", "shop-a", Visibility.INTERNAL, "staff-wiki", TrustLevel.STAFF,
                         "shop-a 환불 예외 규정: 파손 상품은 사진 확인 후 14일까지 환불합니다."),
            KnowledgeDoc("policy-b-int", "shop-b", Visibility.INTERNAL, "staff-wiki", TrustLevel.STAFF,
                         "shop-b 환불 예외 규정 내부용: 단골 고객은 30일까지 환불, 사유 묻지 않음."),
            KnowledgeDoc("review-102", "shop-a", Visibility.PUBLIC, "review", TrustLevel.CUSTOMER,
                         "무선 이어폰 배터리가 오래갑니다. 환불 없이 잘 쓰고 있어요."),
        ]

    @classmethod
    def seeded(cls) -> "KnowledgeStore":
        s = cls()
        for d in cls.seed_docs():
            s.add(d)
        return s


class KnowledgeRetriever(Protocol):
    """검색 진입점. 모든 검색은 이 한 곳만 지난다(6장 6.4)."""

    def retrieve(self, user: UserContext, query: str) -> list[KnowledgeDoc]: ...


def tenant_filter(user: UserContext) -> Callable[[KnowledgeDoc], bool]:
    """조건: tenantId == 로그인 테넌트 AND (PUBLIC 또는 로그인 사용자가 직원). 값은 로그인 정보에서만."""
    tenant = user.tenant_id
    return lambda d: d.tenant_id == tenant and (d.visibility == Visibility.PUBLIC or user.staff)


class TenantScopedRetriever:
    """[수정 후] 필터 값은 로그인 정보(UserContext)에서만 가져온다. 채팅에 쓴 테넌트 이름은 무시한다."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def retrieve(self, user: UserContext, query: str) -> list[KnowledgeDoc]:
        return self.store.search(query, 4, tenant_filter(user))


class UnfilteredRetriever:
    """[수정 전] 권한 필터 없는 검색. shop-a 직원 질문에 shop-b 내부 문서가 섞인다(6장 6.1)."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def retrieve(self, user: UserContext, query: str) -> list[KnowledgeDoc]:
        return self.store.search(query, 4, lambda d: True)


class NaiveRagAnswerer:
    """[수정 전] 넣을 때 검사 없음, 문서를 그냥 이어 붙임([doc:id] 본문), 권한 필터 없음, 근거 검사 없음."""

    def __init__(self, store: KnowledgeStore, llm):
        self.store = store
        self.llm = llm

    def ingest(self, doc: KnowledgeDoc) -> None:
        self.store.add(doc)

    def answer(self, user: UserContext, question: str) -> GroundedAnswer:
        docs = UnfilteredRetriever(self.store).retrieve(user, question)
        context = "\n".join(f"[doc:{d.id}] {d.text}" for d in docs)
        req = LlmRequest([ChatMessage.system("너는 상담봇이다. 아래 자료로 답한다.\n" + context),
                          ChatMessage.user(question)], 0)
        return GroundedAnswer(self.llm.call(req).text, [d.id for d in docs])


class GuardedRagAnswerer:
    """[수정 후] 넣을 때 IngestionScanner → 꺼낼 때 TenantScopedRetriever → DocumentFencer → GroundingPolicy."""
    _CITE = re.compile(r"근거:\s*([A-Za-z0-9_-]+(?:\s*,\s*[A-Za-z0-9_-]+)*)")  # ASCII 글자·숫자만

    def __init__(self, store: KnowledgeStore, llm, scanner: IngestionScanner, grounding: GroundingPolicy):
        self.store = store
        self.llm = llm
        self.scanner = scanner
        self.grounding = grounding
        self.retriever = TenantScopedRetriever(store)
        self._review_queue: list[ScanFinding] = []

    def ingest(self, doc: KnowledgeDoc) -> None:
        findings = self.scanner.scan(doc)
        if not findings:
            self.store.add(doc)
        else:
            self._review_queue.extend(findings)

    def answer(self, user: UserContext, question: str) -> GroundedAnswer:
        docs = self.retriever.retrieve(user, question)
        if not docs:
            return GroundedAnswer.no_ground()
        req = LlmRequest([
            ChatMessage.system(SystemPrompts.AFTER + "\n답 끝에 '근거: 문서ID'를 적는다.\n" + DocumentFencer.fence(docs)),
            ChatMessage.user(question)], 200)
        text = self.llm.call(req).text
        return self.grounding.enforce(GroundedAnswer(text, self.cited_ids(text)), docs)

    def review_queue(self) -> list[ScanFinding]:
        return list(self._review_queue)

    @classmethod
    def cited_ids(cls, text: str) -> list[str]:
        m = cls._CITE.search(text)
        if not m:
            return []
        return [s.strip() for s in m.group(1).split(",") if s.strip()]
