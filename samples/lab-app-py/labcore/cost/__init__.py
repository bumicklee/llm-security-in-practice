"""7~8장 요금 폭탄 방어 부품과 수정 전/후 쌍."""
import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from labcore.injection import InputGuard, Intent
from labcore.llm import ChatMessage, LlmRequest, Usage, count_tokens
from labcore.user import UserContext


class FakePricing:
    """가짜 단가로 예상 청구액 계산(7장 7.2). 입력 1,000토큰 = 10원, 출력 1,000토큰 = 30원(가짜)."""
    FAKE_INPUT_KRW_PER_1K = 10.0
    FAKE_OUTPUT_KRW_PER_1K = 30.0

    @classmethod
    def krw(cls, u: Usage) -> float:
        return u.prompt_tokens / 1000.0 * cls.FAKE_INPUT_KRW_PER_1K + u.completion_tokens / 1000.0 * cls.FAKE_OUTPUT_KRW_PER_1K


class RetryAmplification:
    """재시도가 겹치면 실패 한 번이 호출 몇 번이 되는지 계산(7장 7.3, 8장 8.3).

    인자는 층마다 "시도 횟수"(첫 시도 + 재시도). openai Python SDK 3.40.0의 DEFAULT_MAX_RETRIES = 2 → 시도 3번.
    앞단(게이트웨이·클라이언트)이 3번 시도하면 최악 3 × 3 = 9번. max_retries=1이면 3 × 2 = 6번.
    """

    @staticmethod
    def worst_case_calls(*attempts_per_layer: int) -> int:
        total = 1
        for a in attempts_per_layer:
            total *= max(1, a)
        return total


class ConversationWindow:
    """대화 기록 자르기(8장 8.3). 기본 20개 창.
    랩 수정 전 코드는 일부러 무제한으로 저장해 입력 토큰이 계단처럼 늘게 했다(7장 7.2)."""
    DEFAULT_MAX_MESSAGES = 20

    @staticmethod
    def last_n(history: list, max_messages: int) -> list:
        return list(history) if len(history) <= max_messages else list(history[len(history) - max_messages:])


class CostAlert:
    """하루 예산의 일정 비율에서 경보(8장 8.5). 같은 경보는 하루 한 번. shopbot은 prometheus 카운터로 같은 계산."""

    def __init__(self, daily_budget_krw: float, *thresholds: float):
        self.daily_budget_krw = daily_budget_krw
        self.thresholds = list(thresholds)
        self._fired: list[str] = []
        self._lock = threading.Lock()

    def evaluate(self, spent_today_krw: float) -> list[str]:
        now = []
        with self._lock:
            for t in self.thresholds:
                name = f"COST_{round(t * 100)}PCT"
                if spent_today_krw >= self.daily_budget_krw * t and name not in self._fired:
                    self._fired.append(name)
                    now.append(name)
        return now


class UsageLedger:
    """사용자별·테넌트별·전체 "오늘" 토큰 합계(7장 7.5, 8장 8.2). 한 서버용. 여러 서버면 Redis로 옮긴다."""

    def __init__(self, today: Callable[[], date] = date.today):
        self._today = today
        self._by_key: dict[str, int] = {}
        self._lock = threading.Lock()

    def _key(self, k: str) -> str:
        return f"{self._today().isoformat()}|{k}"

    def add(self, user_id: str, tenant_id: str, u: Usage) -> None:
        t = u.total_tokens
        with self._lock:
            for k in (f"user:{user_id}", f"tenant:{tenant_id}", "global"):
                kk = self._key(k)
                self._by_key[kk] = self._by_key.get(kk, 0) + t

    def _get(self, k: str) -> int:
        with self._lock:
            return self._by_key.get(self._key(k), 0)

    def user_today(self, user_id: str) -> int:
        return self._get(f"user:{user_id}")

    def tenant_today(self, tenant_id: str) -> int:
        return self._get(f"tenant:{tenant_id}")

    def global_today(self) -> int:
        return self._get("global")

    def reset(self) -> None:
        """평가 키트 reset용(eval 프로필): 오늘 사용량을 0으로."""
        with self._lock:
            self._by_key.clear()


@dataclass(frozen=True)
class Limits:
    per_request_input: int
    per_user_daily: int
    per_tenant_daily: int
    global_daily: int

    @staticmethod
    def lab_defaults() -> "Limits":
        return Limits(1_000, 20_000, 200_000, 1_000_000)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    user_remaining: int


class TokenBudget:
    """토큰 한도 3단계(요청당·사용자 하루·서비스 전체 하루)(8장 8.2, 표 8-1). 값은 예시다."""
    Limits = Limits

    def __init__(self, limits: Limits, ledger: UsageLedger):
        self.limits = limits
        self.ledger = ledger

    def check(self, user: UserContext, estimated_input_tokens: int) -> Decision:
        used = self.ledger.user_today(user.user_id)
        remaining = max(0, self.limits.per_user_daily - used)
        if estimated_input_tokens > self.limits.per_request_input:
            return Decision(False, "REQUEST_TOO_LARGE", remaining)
        if used + estimated_input_tokens > self.limits.per_user_daily:
            return Decision(False, "USER_DAILY_LIMIT", remaining)
        if self.ledger.tenant_today(user.tenant_id) + estimated_input_tokens > self.limits.per_tenant_daily:
            return Decision(False, "TENANT_DAILY_LIMIT", remaining)
        if self.ledger.global_today() + estimated_input_tokens > self.limits.global_daily:
            return Decision(False, "GLOBAL_DAILY_LIMIT", remaining)
        return Decision(True, "ok", remaining)


@dataclass(frozen=True)
class RateResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class UserRateLimiter:
    """사용자 ID 기준 레이트 리밋(8장 8.1). 직접 만든 토큰 버킷(탐욕 충전, Bucket4j refillGreedy와 같은 뜻).

    - 키는 IP가 아니라 로그인 사용자 ID다(slowapi는 key_func가 필수 인자이고 흔히 넘기는 get_remote_address가 IP 기준이라 그대로 쓰지 않는다).
    - 여러 서버면 공유 저장소로 바꾼다(redis 프로필: limits + Redis).
    clock_ns: 나노초를 돌려주는 함수. 테스트는 멈춘 시계를 넣는다.
    """

    def __init__(self, capacity: int, period_seconds: float, clock_ns: Callable[[], int] = time.monotonic_ns):
        self.capacity = capacity
        self.period_ns = int(period_seconds * 1_000_000_000)
        self.clock_ns = clock_ns
        self._buckets: dict[str, list] = {}   # key → [tokens(float), last_ns]
        self._lock = threading.Lock()

    @classmethod
    def lab_defaults(cls) -> "UserRateLimiter":
        """랩 기본값: 1분에 10번."""
        return cls(10, 60)

    def try_acquire(self, key: str) -> RateResult:
        now = self.clock_ns()
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = self._buckets[key] = [float(self.capacity), now]
            elapsed = max(0, now - b[1])
            b[0] = min(float(self.capacity), b[0] + elapsed * self.capacity / self.period_ns)
            b[1] = now
            if b[0] >= 1.0:
                b[0] -= 1.0
                return RateResult(True, int(math.floor(b[0])), 0)
            wait_ns = (1.0 - b[0]) * self.period_ns / self.capacity
            return RateResult(False, 0, max(1, int(wait_ns // 1_000_000_000)))

    def reset(self) -> None:
        """평가 키트 reset용(eval 프로필): 모든 버킷을 비운다."""
        with self._lock:
            self._buckets.clear()


@dataclass(frozen=True)
class Reply:
    """채팅 API 앞문의 응답. status는 HTTP 상태 코드 흉내."""
    status: int
    body: str
    user_tokens_today: int


class OpenGateway:
    """[수정 전] 횟수 제한 없음, 토큰 한도 없음, 대화 기록 무제한 저장, 최대 출력 토큰 없음(7장 재현용)."""

    def __init__(self, llm, ledger: UsageLedger):
        self.llm = llm
        self.ledger = ledger
        self._history: dict[str, list] = {}

    def handle(self, user: UserContext, message: str) -> Reply:
        h = self._history.setdefault(user.user_id, [])
        h.append(ChatMessage.user(message))
        msgs = [ChatMessage.system("너는 쇼핑몰 상담봇이다.")] + h   # 통째로 다시 보냄
        r = self.llm.call(LlmRequest(msgs, 0))
        h.append(ChatMessage.assistant(r.text))
        self.ledger.add(user.user_id, user.tenant_id, r.usage)
        return Reply(200, r.text, self.ledger.user_today(user.user_id))

    def history_size(self, user_id: str) -> int:
        return len(self._history.get(user_id, []))


class LimitedGateway:
    """[수정 후] 8장의 방어를 차례로: 레이트 리밋 → 입력 길이 → 토큰 한도 → 대화 창·최대 출력 → 사용량 기록."""

    def __init__(self, llm, ledger: UsageLedger, rate_limiter: UserRateLimiter, budget: TokenBudget,
                 input_guard: InputGuard, window_size: int, max_output_tokens: int):
        self.llm = llm
        self.ledger = ledger
        self.rate_limiter = rate_limiter
        self.budget = budget
        self.input_guard = input_guard
        self.window_size = window_size
        self.max_output_tokens = max_output_tokens
        self._history: dict[str, list] = {}
        self._lock = threading.Lock()

    def handle(self, user: UserContext, message: str) -> Reply:
        rl = self.rate_limiter.try_acquire(user.user_id)
        if not rl.allowed:
            return Reply(429, f"요청이 너무 잦습니다. {rl.retry_after_seconds}초 뒤 다시 시도하세요.",
                         self.ledger.user_today(user.user_id))
        if not self.input_guard.check(message).allowed:
            return Reply(400, "입력을 처리할 수 없습니다.", self.ledger.user_today(user.user_id))
        h = self._history.setdefault(user.user_id, [])
        msgs = [ChatMessage.system("너는 쇼핑몰 상담봇이다.")] + ConversationWindow.last_n(h, self.window_size) \
            + [ChatMessage.user(message)]
        estimated = sum(count_tokens(m.text) for m in msgs)
        d = self.budget.check(user, estimated)
        if not d.allowed:
            return Reply(429, f"오늘 사용 한도에 닿았습니다({d.reason}). 남은 양: {d.user_remaining}토큰",
                         self.ledger.user_today(user.user_id))
        r = self.llm.call(LlmRequest(msgs, self.max_output_tokens))
        with self._lock:
            h.append(ChatMessage.user(message))
            h.append(ChatMessage.assistant(r.text))
        self.ledger.add(user.user_id, user.tenant_id, r.usage)
        return Reply(200, r.text, self.ledger.user_today(user.user_id))


def normalize(q: str) -> str:
    return re.sub(r"[\s?!.]+", " ", q.lower()).strip()


class SharedKeyCache:
    """[수정 전] 키 = 정규화한 질문. "내 주문 어디까지 왔어?"가 사용자 구분 없이 같은 키 → bob이 alice의 답을 받는다(8장 8.4)."""

    def __init__(self):
        self._map: dict[str, str] = {}

    def get(self, user: UserContext, q: str) -> str | None:
        return self._map.get(normalize(q))

    def put(self, user: UserContext, q: str, intent: Intent, a: str) -> None:
        self._map[normalize(q)] = a


class ScopedCache:
    """[수정 후] 키 = 테넌트|사용자|질문, 그리고 개인 정보가 든 의도(주문 조회 등)는 아예 캐시하지 않는다."""

    def __init__(self):
        self._map: dict[str, str] = {}

    @staticmethod
    def _key(u: UserContext, q: str) -> str:
        return f"{u.tenant_id}|{u.user_id}|{normalize(q)}"

    def get(self, user: UserContext, q: str) -> str | None:
        return self._map.get(self._key(user, q))

    def put(self, user: UserContext, q: str, intent: Intent, a: str) -> None:
        if intent in (Intent.ORDER_STATUS, Intent.CANCEL_REQUEST):
            return   # 개인 답은 캐시 안 함
        self._map[self._key(user, q)] = a


class ResponseCache:
    """두 구현을 한 이름 아래에. 랩 단순화: 시맨틱 대신 정규화 문자열 일치."""
    SharedKeyCache = SharedKeyCache
    ScopedCache = ScopedCache
    normalize = staticmethod(normalize)
