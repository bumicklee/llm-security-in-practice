"""9장 도구 권한과 22장 쿠폰 도구.

user는 "모델 인자"가 아니라 서버가 넘기는 보안 컨텍스트다(shopbot에서는 ToolRuntime[LabContext]).
"""
import re
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from labcore.audit import AuditLog
from labcore.user import UserContext


class OrderStatus(str, Enum):
    PAID = "PAID"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"


class ToolRisk(str, Enum):
    """도구 권한 등급(9장 표 9-1). READ 바로 실행 / CHANGE 사용자 확인 / MONEY 사람 승인 후 실행."""
    READ = "READ"
    CHANGE = "CHANGE"
    MONEY = "MONEY"


@dataclass(frozen=True)
class Order:
    """가짜 주문. alice=1001·1002, bob=2001, carol=3001(랩 시드)."""
    id: str
    owner_id: str
    tenant_id: str
    status: OrderStatus
    amount_krw: int

    def with_status(self, s: OrderStatus) -> "Order":
        return replace(self, status=s)

    def to_json(self) -> dict:
        return {"id": self.id, "ownerId": self.owner_id, "tenantId": self.tenant_id,
                "status": self.status.value, "amountKrw": self.amount_krw}


class OrderRepository:
    """메모리 주문 저장소(랩용)."""

    def __init__(self):
        self._orders: dict[str, Order] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _seed() -> list[Order]:
        return [Order("1001", "alice", "shop-a", OrderStatus.PAID, 39_000),
                Order("1002", "alice", "shop-a", OrderStatus.SHIPPING, 12_000),
                Order("2001", "bob", "shop-a", OrderStatus.PAID, 25_000),
                Order("3001", "carol", "shop-b", OrderStatus.PAID, 18_000)]

    @classmethod
    def seeded(cls) -> "OrderRepository":
        r = cls()
        for o in cls._seed():
            r.save(o)
        return r

    def find(self, order_id) -> Order | None:
        with self._lock:
            return self._orders.get(order_id)

    def save(self, o: Order) -> None:
        with self._lock:
            self._orders[o.id] = o

    def reset_to_seed(self) -> None:
        """평가 키트 reset용: 시드 상태로 되돌린다(5-1에서 바뀐 주문 상태도 원래대로)."""
        with self._lock:
            self._orders = {o.id: o for o in self._seed()}


@dataclass(frozen=True)
class ToolResult:
    """도구가 모델에게 돌려주는 결과. 실패 사유는 모델에게도 짧게만 알린다."""
    ok: bool
    message: str
    pending_action_id: str | None = None

    @staticmethod
    def success(m: str) -> "ToolResult":
        return ToolResult(True, m, None)

    @staticmethod
    def denied(m: str) -> "ToolResult":
        return ToolResult(False, m, None)

    @staticmethod
    def pending(m: str, action_id: str) -> "ToolResult":
        return ToolResult(True, m, action_id)

    def to_json(self) -> dict:
        return {"ok": self.ok, "message": self.message, "pendingActionId": self.pending_action_id}

    @property
    def status(self) -> str:
        """eval 도구 기록의 상태: PROPOSED(승인 대기) · EXECUTED(실행됨) · DENIED(앱이 막음)."""
        if self.pending_action_id is not None:
            return "PROPOSED"
        return "EXECUTED" if self.ok else "DENIED"


class ToolArgValidator:
    """모델이 만든 도구 인자를 사용자 입력처럼 검증(9장 9.5).

    orderId 숫자 4~10자리 / quantity 1~10 / couponCode 대문자·숫자·하이픈 4~20자 / amount 원 단위 양의 정수(1~7자리).
    한도(1만 원)는 형식이 아니라 정책이라 AuthorizedCouponTools가 본다(22장).
    """
    _ORDER_ID = re.compile(r"[0-9]{4,10}")
    _COUPON = re.compile(r"[A-Z0-9-]{4,20}")
    _AMOUNT = re.compile(r"[1-9][0-9]{0,6}")

    @classmethod
    def valid_order_id(cls, v) -> bool:
        return isinstance(v, str) and cls._ORDER_ID.fullmatch(v) is not None

    @staticmethod
    def valid_quantity(q: int) -> bool:
        return 1 <= q <= 10

    @classmethod
    def valid_coupon(cls, v) -> bool:
        return isinstance(v, str) and cls._COUPON.fullmatch(v) is not None

    @classmethod
    def valid_amount(cls, v) -> bool:
        return isinstance(v, str) and cls._AMOUNT.fullmatch(v.strip()) is not None


class ToolAllowlist:
    """등록한 도구만 호출 가능(9장 9.5). shopbot은 시작할 때 @tool 이름이 모두 여기 있는지 확인한다(registry_check)."""

    def __init__(self, tools: dict[str, ToolRisk]):
        self._tools = dict(tools)

    @staticmethod
    def lab() -> "ToolAllowlist":
        return ToolAllowlist({"getOrderStatus": ToolRisk.READ, "cancelOrder": ToolRisk.MONEY,
                              "issueCoupon": ToolRisk.MONEY,   # 22장. 돈이 걸린 도구 → 직원 승인
                              "summarizeUrl": ToolRisk.READ})

    def risk_of(self, name: str) -> ToolRisk | None:
        return self._tools.get(name)

    def allowed(self, name: str) -> bool:
        return name in self._tools


class State(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PendingAction:
    id: str
    tool_name: str
    requested_by: str
    tenant_id: str | None
    order_id: str
    amount_krw: int
    risk: ToolRisk
    created_at: datetime
    state: State
    decided_by: str | None

    def to_json(self) -> dict:
        return {"id": self.id, "toolName": self.tool_name, "requestedBy": self.requested_by,
                "tenantId": self.tenant_id, "orderId": self.order_id, "amountKrw": self.amount_krw,
                "risk": self.risk.value, "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
                "state": self.state.value, "decidedBy": self.decided_by}


class ApprovalQueue:
    """위험 도구의 "제안"을 담아 두는 승인 대기열(9장 9.4, 22장). 도구는 실행하지 않고 여기에 넣기만 한다.

    LangChain HumanInTheLoopMiddleware는 체크포인터가 있어야 하는 프레임워크 승인 기능이다. 그래도 서버가
    승인 순간에 상태를 다시 확인하고 기록을 남겨야 한다는 원칙은 같다(곁글, 9장).
    """
    State = State

    def __init__(self):
        self._actions: dict[str, PendingAction] = {}
        self._lock = threading.Lock()

    def propose(self, tool_name: str, requested_by: str, order_id: str, risk: ToolRisk,
                tenant_id: str | None = None, amount_krw: int = 0) -> PendingAction:
        a = PendingAction(str(uuid.uuid4()), tool_name, requested_by, tenant_id, order_id, amount_krw, risk,
                          datetime.now(timezone.utc), State.PENDING, None)
        with self._lock:
            self._actions[a.id] = a
        return a

    def find(self, action_id: str) -> PendingAction | None:
        with self._lock:
            return self._actions.get(action_id)

    def pending_for(self, user_id: str) -> list[PendingAction]:
        """고객 화면의 목록: 내가 요청한 PENDING만."""
        with self._lock:
            return [a for a in self._actions.values() if a.state == State.PENDING and a.requested_by == user_id]

    def pending_for_staff(self, staff_id: str, tenant_id: str, tool_name: str) -> list[PendingAction]:
        """직원 화면의 목록: 내 테넌트의 PENDING 중 이 도구만, 내가 요청한 것은 뺀다."""
        with self._lock:
            return [a for a in self._actions.values()
                    if a.state == State.PENDING and a.tool_name == tool_name
                    and a.tenant_id == tenant_id and a.requested_by != staff_id]

    def has_pending(self, tool_name: str, order_id: str) -> bool:
        """같은 주문에 같은 도구의 PENDING이 이미 있는가(쿠폰 주문당 1회, 22장 T4)."""
        with self._lock:
            return any(a.state == State.PENDING and a.tool_name == tool_name and a.order_id == order_id
                       for a in self._actions.values())

    def decide(self, action_id: str, s: State, by: str) -> PendingAction | None:
        """PENDING일 때만 한 번 결정할 수 있다(두 번 승인 방지)."""
        with self._lock:
            a = self._actions.get(action_id)
            if a is None or a.state != State.PENDING:
                return None
            d = replace(a, state=s, decided_by=by)
            self._actions[action_id] = d
            return d

    def clear(self) -> None:
        with self._lock:
            self._actions.clear()


@dataclass(frozen=True)
class Coupon:
    order_id: str
    amount_krw: int
    requested_by: str
    approved_by: str
    issued_at: datetime

    def to_json(self) -> dict:
        return {"orderId": self.order_id, "amountKrw": self.amount_krw, "requestedBy": self.requested_by,
                "approvedBy": self.approved_by, "issuedAt": self.issued_at.isoformat().replace("+00:00", "Z")}


class CouponLedger:
    """발급한 쿠폰 장부(22장 할 일 #6). 주문당 1장. 평가 키트 reset이 비운다."""

    def __init__(self):
        self._by_order: dict[str, Coupon] = {}
        self._lock = threading.Lock()

    def issue(self, order_id: str, amount_krw: int, requested_by: str, approved_by: str) -> bool:
        """주문당 1장. 이미 있으면 False(아무것도 바꾸지 않음)."""
        with self._lock:
            if order_id in self._by_order:
                return False
            self._by_order[order_id] = Coupon(order_id, amount_krw, requested_by, approved_by, datetime.now(timezone.utc))
            return True

    def _overwrite(self, order_id, amount_krw, requested_by, approved_by) -> None:
        """수정 전 구현만 쓴다: 주문당 1회 검사 없이 덮어쓴다."""
        with self._lock:
            self._by_order[order_id] = Coupon(order_id, amount_krw, requested_by, approved_by, datetime.now(timezone.utc))

    def issued_for(self, order_id: str) -> Coupon | None:
        with self._lock:
            return self._by_order.get(order_id)

    def all(self) -> list[Coupon]:
        with self._lock:
            return list(self._by_order.values())

    def count(self) -> int:
        with self._lock:
            return len(self._by_order)

    def reset(self) -> None:
        with self._lock:
            self._by_order.clear()


class TrustingOrderTools:
    """[수정 전] 모델이 고른 orderId를 그대로 믿는다 → IDOR(9장 9.1~9.2). user를 받기는 하지만 쓰지 않는다."""

    def __init__(self, repo: OrderRepository):
        self.repo = repo

    def get_order_status(self, user: UserContext, order_id) -> ToolResult:
        o = self.repo.find(order_id)
        return ToolResult.success(f"주문 {o.id}: {o.status.value}") if o else ToolResult.denied("주문을 찾을 수 없습니다")

    def cancel_order(self, user: UserContext, order_id) -> ToolResult:
        o = self.repo.find(order_id)
        if o is None:
            return ToolResult.denied("주문을 찾을 수 없습니다")
        self.repo.save(o.with_status(OrderStatus.CANCELLED))
        return ToolResult.success(f"주문 {o.id} 취소 완료")


class AuthorizedOrderTools:
    """[수정 후] 9장의 방어: 인자 검증 → 소유권(UserContext 기준, 남의 주문은 "없음"과 같은 문구)
    → 취소는 MONEY 등급이라 승인 대기열에 "제안"만 → 모든 호출을 감사 로그에."""
    NOT_FOUND = "본인 주문만 조회·취소할 수 있습니다"

    def __init__(self, repo: OrderRepository, approvals: ApprovalQueue, audit: AuditLog):
        self.repo = repo
        self.approvals = approvals
        self.audit = audit

    def _owned(self, user: UserContext, order_id) -> Order | None:
        o = self.repo.find(order_id)
        return o if o and o.owner_id == user.user_id and o.tenant_id == user.tenant_id else None

    def get_order_status(self, user: UserContext, order_id) -> ToolResult:
        self.audit.tool_call(user.user_id, "getOrderStatus", f"orderId={_s(order_id)}")
        if not ToolArgValidator.valid_order_id(order_id):
            return ToolResult.denied("주문 번호 형식이 아닙니다")
        o = self._owned(user, order_id)
        return ToolResult.success(f"주문 {o.id}: {o.status.value}") if o else ToolResult.denied(self.NOT_FOUND)

    def cancel_order(self, user: UserContext, order_id) -> ToolResult:
        self.audit.tool_call(user.user_id, "cancelOrder", f"orderId={_s(order_id)}")
        if not ToolArgValidator.valid_order_id(order_id):
            return ToolResult.denied("주문 번호 형식이 아닙니다")
        o = self._owned(user, order_id)
        if o is None:
            self.audit.denied(user.user_id, "cancelOrder", f"not-owner orderId={order_id}")
            return ToolResult.denied(self.NOT_FOUND)
        if o.status != OrderStatus.PAID:
            return ToolResult.denied(f"지금 상태에서는 취소할 수 없습니다({o.status.value})")
        a = self.approvals.propose("cancelOrder", user.user_id, order_id, ToolRisk.MONEY, user.tenant_id, 0)
        # 채팅 요청 ID ↔ 승인 요청을 actionId로 잇는다
        self.audit.proposed(user.user_id, "cancelOrder", f"actionId={a.id} orderId={order_id}")
        return ToolResult.pending(f"주문 {order_id}을 취소할까요? [승인] [거절]", a.id)


class AuthorizedCouponTools:
    """[수정 후] 쿠폰 발급 도구의 방어(22장 22.3). 발급하지 않고 "제안"만 한다.

    1) 인자 검증 2) 소유권(UserContext 기준) 3) 한도: 한 장 최대 1만 원, 주문당 1회
    4) MONEY → 승인 대기열(PROPOSED). 발급은 같은 테넌트 직원이 승인할 때 5) 모든 호출·거부·제안을 감사 로그에
    """
    TOOL = "issueCoupon"
    MAX_AMOUNT_KRW = 10_000
    NOT_FOUND = "본인 주문에만 쿠폰을 요청할 수 있습니다"

    def __init__(self, repo: OrderRepository, approvals: ApprovalQueue, ledger: CouponLedger, audit: AuditLog):
        self.repo = repo
        self.approvals = approvals
        self.ledger = ledger
        self.audit = audit

    def issue_coupon(self, user: UserContext, order_id, amount_krw) -> ToolResult:
        self.audit.tool_call(user.user_id, self.TOOL, f"orderId={_s(order_id)} amountKrw={_s(amount_krw)}")
        if not ToolArgValidator.valid_order_id(order_id):
            return self._deny(user, "bad-orderId", "주문 번호 형식이 아닙니다")
        if not ToolArgValidator.valid_amount(amount_krw):
            return self._deny(user, f"bad-amount orderId={order_id}", "금액은 원 단위 정수여야 합니다")
        amount = int(amount_krw.strip())
        o = self.repo.find(order_id)
        if not (o and o.owner_id == user.user_id and o.tenant_id == user.tenant_id):
            return self._deny(user, f"not-owner orderId={order_id}", self.NOT_FOUND)
        if amount > self.MAX_AMOUNT_KRW:
            return self._deny(user, f"over-limit orderId={order_id} amountKrw={amount}",
                              f"쿠폰은 한 장에 {self.MAX_AMOUNT_KRW}원까지입니다")
        if self.ledger.issued_for(order_id) is not None or self.approvals.has_pending(self.TOOL, order_id):
            return self._deny(user, f"once-per-order orderId={order_id}", "이 주문에는 이미 쿠폰 요청이 있습니다(주문당 1회)")
        a = self.approvals.propose(self.TOOL, user.user_id, order_id, ToolRisk.MONEY, user.tenant_id, amount)
        self.audit.proposed(user.user_id, self.TOOL, f"actionId={a.id} orderId={order_id} amountKrw={amount}")
        return ToolResult.pending(f"주문 {order_id} 쿠폰 {amount}원 발급을 요청했습니다. 직원 승인 후 발급됩니다", a.id)

    def _deny(self, user: UserContext, why: str, message: str) -> ToolResult:
        self.audit.denied(user.user_id, self.TOOL, why)
        return ToolResult.denied(message)


class TrustingCouponTools:
    """[수정 전] 모델이 고른 orderId·amountKrw를 그대로 믿고 바로 발급한다(22장 T1·T2·T4).
    소유권·한도·승인 없음. 같은 주문에 두 번 요청하면 앞 쿠폰을 지우고 다시 발급한다."""

    def __init__(self, repo: OrderRepository, ledger: CouponLedger):
        self.repo = repo
        self.ledger = ledger

    def issue_coupon(self, user: UserContext, order_id, amount_krw) -> ToolResult:
        if self.repo.find(order_id) is None:
            return ToolResult.denied("주문을 찾을 수 없습니다")
        try:
            amount = int(str(amount_krw).strip())
        except ValueError:
            amount = 5_000   # 금액이 이상하면 기본값으로 그냥 발급(수정 전의 "친절함")
        self.ledger._overwrite(order_id, amount, user.user_id, "(승인 없음)")
        return ToolResult.success(f"주문 {order_id} 쿠폰 {amount}원 발급 완료")


class Approver(str, Enum):
    REQUESTER = "REQUESTER"
    TENANT_STAFF = "TENANT_STAFF"
    NONE = "NONE"


class ApprovalService:
    """[승인] 버튼(REST)이 부르는 실행부(9장 9.4, 22장 22.3). LLM은 이 경로에 관여하지 않는다.

    승인하는 순간 소유권·상태·한도를 "다시" 확인한다. 이미 결정된 요청은 다시 결정할 수 없다.
    cancelOrder → REQUESTER(요청한 고객 본인) / issueCoupon → TENANT_STAFF(요청자 ≠ 승인자, 같은 테넌트 직원) / 그 밖 → 없음
    """
    Approver = Approver

    def __init__(self, repo: OrderRepository, approvals: ApprovalQueue, audit: AuditLog,
                 coupons: CouponLedger | None = None):
        self.repo = repo
        self.approvals = approvals
        self.audit = audit
        self.coupons = coupons if coupons is not None else CouponLedger()

    @staticmethod
    def approver_of(tool_name: str) -> Approver:
        if tool_name == "cancelOrder":
            return Approver.REQUESTER
        if tool_name == AuthorizedCouponTools.TOOL:
            return Approver.TENANT_STAFF
        return Approver.NONE

    @classmethod
    def may_decide(cls, user: UserContext, a: PendingAction) -> bool:
        who = cls.approver_of(a.tool_name)
        if who == Approver.REQUESTER:
            return a.requested_by == user.user_id
        if who == Approver.TENANT_STAFF:
            return (user.staff and a.requested_by != user.user_id      # 요청자 ≠ 승인자
                    and user.tenant_id == a.tenant_id)                 # 같은 테넌트 직원만
        return False

    def approve(self, user: UserContext, action_id: str) -> ToolResult:
        a = self.approvals.find(action_id)
        if a is None:
            return ToolResult.denied("승인할 수 없는 요청입니다")
        if not self.may_decide(user, a):
            self.audit.denied(user.user_id, a.tool_name, f"approve-not-allowed actionId={action_id} requestedBy={a.requested_by}")
            return ToolResult.denied("이 요청은 요청자가 아닌 같은 매장 직원만 승인할 수 있습니다"
                                     if self.approver_of(a.tool_name) == Approver.TENANT_STAFF else "승인할 수 없는 요청입니다")
        if a.tool_name == "cancelOrder":
            return self._approve_cancel(user, a)
        if a.tool_name == AuthorizedCouponTools.TOOL:
            return self._approve_coupon(user, a)
        return ToolResult.denied("승인할 수 없는 요청입니다")

    def _approve_cancel(self, user: UserContext, a: PendingAction) -> ToolResult:
        o = self.repo.find(a.order_id)
        if not (o and o.owner_id == user.user_id and o.tenant_id == user.tenant_id):
            return ToolResult.denied("승인할 수 없는 요청입니다")
        if o.status != OrderStatus.PAID:
            return ToolResult.denied(f"지금 상태에서는 취소할 수 없습니다({o.status.value})")
        if self.approvals.decide(a.id, State.APPROVED, user.user_id) is None:
            return ToolResult.denied("이미 처리된 요청입니다")
        self.repo.save(o.with_status(OrderStatus.CANCELLED))
        self.audit.approved(user.user_id, a.tool_name, f"actionId={a.id} orderId={a.order_id}")
        return ToolResult.success(f"주문 {a.order_id} 취소 완료")

    def _approve_coupon(self, staff: UserContext, a: PendingAction) -> ToolResult:
        # 다시 확인: 주문이 아직 요청자의 것이고 직원과 같은 테넌트인가, 한도 안인가, 이미 발급되지 않았나
        o = self.repo.find(a.order_id)
        if not (o and o.owner_id == a.requested_by and o.tenant_id == staff.tenant_id):
            return ToolResult.denied("승인할 수 없는 요청입니다")
        if a.amount_krw < 1 or a.amount_krw > AuthorizedCouponTools.MAX_AMOUNT_KRW:
            return ToolResult.denied("한도를 넘는 금액입니다")
        if self.coupons.issued_for(a.order_id) is not None:
            return ToolResult.denied("이 주문에는 이미 쿠폰이 발급됐습니다(주문당 1회)")
        if self.approvals.decide(a.id, State.APPROVED, staff.user_id) is None:
            return ToolResult.denied("이미 처리된 요청입니다")
        if not self.coupons.issue(a.order_id, a.amount_krw, a.requested_by, staff.user_id):
            return ToolResult.denied("이 주문에는 이미 쿠폰이 발급됐습니다(주문당 1회)")
        self.audit.approved(staff.user_id, a.tool_name,
                            f"actionId={a.id} orderId={a.order_id} amountKrw={a.amount_krw} requestedBy={a.requested_by}")
        return ToolResult.success(f"쿠폰 발급 완료: 주문 {a.order_id} · {a.amount_krw}원 · 요청 {a.requested_by} · 승인 {staff.user_id}")

    def reject(self, user: UserContext, action_id: str) -> ToolResult:
        a = self.approvals.find(action_id)
        if a is None or not self.may_decide(user, a):
            return ToolResult.denied("거절할 수 없는 요청입니다")
        if self.approvals.decide(action_id, State.REJECTED, user.user_id) is None:
            return ToolResult.denied("이미 처리된 요청입니다")
        self.audit.rejected(user.user_id, a.tool_name, f"actionId={action_id}")
        return ToolResult.success("쿠폰 요청을 거절했습니다" if a.tool_name == AuthorizedCouponTools.TOOL else "취소 요청을 거절했습니다")


def _s(v) -> str:
    """None은 "null" 글자로 바꾼다(감사 로그·응답 글자를 고정)."""
    return "null" if v is None else str(v)
