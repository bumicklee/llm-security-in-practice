"""22장 종합 실습의 pytest 2개. 쿠폰 발급 도구(ToolRisk.MONEY)의 소유권·직원 승인·승인자 분리·한도·주문당 1회.
--lab-target=before 이면 수정 전 구현(TrustingCouponTools: 확인 없이 바로 발급) → 두 테스트 모두 빨강.
실행: pytest -m capstone [--lab-target=before]
"""
import pytest

from labcore import target
from labcore.audit import AuditLog
from labcore.tools import (ApprovalQueue, ApprovalService, AuthorizedCouponTools, CouponLedger, OrderRepository,
                           TrustingCouponTools)
from labcore.user import UserContext

pytestmark = pytest.mark.capstone


@pytest.fixture
def w():
    class W:
        repo = OrderRepository.seeded()
        queue = ApprovalQueue()
        ledger = CouponLedger()
        audit = AuditLog()
    W.tools = TrustingCouponTools(W.repo, W.ledger) if target.is_before() \
        else AuthorizedCouponTools(W.repo, W.queue, W.ledger, W.audit)
    W.approval = ApprovalService(W.repo, W.queue, W.audit, W.ledger)
    return W


def test_남의_주문에는_쿠폰이_나가지_않고_본인_주문도_직원_승인_전에는_발급되지_않는다(w):
    foreign = w.tools.issue_coupon(UserContext.bob(), "1001", "5000")          # T1: bob → alice의 주문
    assert not foreign.ok, "남의 주문(bob → 1001)"
    assert w.ledger.issued_for("1001") is None, "남의 주문에 쿠폰이 나감"

    own = w.tools.issue_coupon(UserContext.alice(), "1001", "5000")            # T2: 본인 주문도 제안만
    assert own.pending_action_id is not None, "본인 주문은 승인 대기(PROPOSED)여야 한다"
    assert w.ledger.count() == 0, "직원 승인 전 발급된 쿠폰 수"

    action_id = own.pending_action_id
    assert not w.approval.approve(UserContext.alice(), action_id).ok, "요청자 본인 승인(T3)"
    assert not w.approval.approve(UserContext.bob(), action_id).ok, "같은 테넌트 고객 승인"
    assert not w.approval.approve(UserContext.carol(), action_id).ok, "다른 테넌트(shop-b) 직원 승인"
    assert w.ledger.count() == 0

    ok = w.approval.approve(UserContext.dave(), action_id)                     # shop-a 직원
    assert ok.ok, "같은 테넌트 직원 dave 승인"
    c = w.ledger.issued_for("1001")
    assert c is not None and c.amount_krw == 5000 and c.requested_by == "alice" and c.approved_by == "dave"
    assert not w.approval.approve(UserContext.dave(), action_id).ok, "두 번 승인"
    assert w.ledger.count() == 1

    # T9: 누가 언제 무엇을 했는지 감사 로그에 남는다(요청·거부·승인)
    seen = [f"{e.type} {e.actor}" for e in w.audit.all()]
    for expected in ["TOOL_DENIED bob", "PROPOSED alice", "TOOL_DENIED alice", "TOOL_DENIED carol", "APPROVED dave"]:
        assert expected in seen


def test_금액_한도와_주문당_1회를_넘지_않는다(w):
    assert not w.tools.issue_coupon(UserContext.alice(), "1001", "10001").ok, "10,001원(한도 1만 원 초과)"
    assert not w.tools.issue_coupon(UserContext.alice(), "1001", "오천").ok, "금액이 숫자가 아님"
    assert not w.tools.issue_coupon(UserContext.alice(), "1001", "0").ok, "0원"
    assert w.ledger.count() == 0, "한도 밖 요청으로 발급된 쿠폰"

    first = w.tools.issue_coupon(UserContext.alice(), "1001", "10000")
    assert first.ok, "1만 원 정확히는 요청 가능"
    assert not w.tools.issue_coupon(UserContext.alice(), "1001", "3000").ok, "같은 주문 두 번째 요청(승인 대기 중)"

    if first.pending_action_id is not None:
        w.approval.approve(UserContext.dave(), first.pending_action_id)
    assert not w.tools.issue_coupon(UserContext.alice(), "1001", "3000").ok, "같은 주문 두 번째 요청(발급 뒤)"
    c = w.ledger.issued_for("1001")
    assert c is not None and c.amount_krw == 10000
