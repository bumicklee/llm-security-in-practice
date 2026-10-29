"""22장 할 일 #4의 단위 확인(수정 후 구현만). --lab-target=before에서도 초록이다
(공격 테스트가 아니라 부품 확인). 실행: pytest -m capstone"""
import pytest

from labcore.audit import AuditLog
from labcore.tools import (ApprovalQueue, ApprovalService, AuthorizedCouponTools, AuthorizedOrderTools, CouponLedger,
                           Order, OrderRepository, OrderStatus, ToolAllowlist, ToolArgValidator, ToolRisk)
from labcore.user import UserContext

pytestmark = pytest.mark.capstone


@pytest.fixture
def w():
    class W:
        repo = OrderRepository.seeded()
        queue = ApprovalQueue()
        ledger = CouponLedger()
        audit = AuditLog()
    W.approval = ApprovalService(W.repo, W.queue, W.audit, W.ledger)
    return W


def test_도구마다_승인자가_다르다():
    assert ApprovalService.approver_of("cancelOrder") == ApprovalService.Approver.REQUESTER
    assert ApprovalService.approver_of("issueCoupon") == ApprovalService.Approver.TENANT_STAFF
    assert ApprovalService.approver_of("summarizeUrl") == ApprovalService.Approver.NONE
    assert ToolAllowlist.lab().risk_of("issueCoupon") == ToolRisk.MONEY


def test_직원이_스스로_요청한_쿠폰도_본인은_승인할_수_없다(w):
    w.repo.save(Order("4001", "dave", "shop-a", OrderStatus.PAID, 9_000))   # 직원이 고객으로 산 주문(가상)
    tools = AuthorizedCouponTools(w.repo, w.queue, w.ledger, w.audit)
    r = tools.issue_coupon(UserContext.dave(), "4001", "3000")
    assert not w.approval.approve(UserContext.dave(), r.pending_action_id).ok, "요청자 = 직원 본인"
    assert w.queue.pending_for_staff("dave", "shop-a", "issueCoupon") == [], "직원 목록에서 내 요청은 빠진다"
    assert w.ledger.count() == 0


def test_직원은_쿠폰_요청을_거절할_수_있고_고객_본인은_거절도_승인도_못_한다(w):
    tools = AuthorizedCouponTools(w.repo, w.queue, w.ledger, w.audit)
    action_id = tools.issue_coupon(UserContext.bob(), "2001", "2000").pending_action_id
    assert len(w.queue.pending_for_staff("dave", "shop-a", "issueCoupon")) == 1
    assert w.queue.pending_for_staff("carol", "shop-b", "issueCoupon") == [], "다른 테넌트 직원 목록"
    assert not w.approval.reject(UserContext.bob(), action_id).ok
    assert w.approval.reject(UserContext.dave(), action_id).ok
    assert not w.approval.approve(UserContext.dave(), action_id).ok, "거절 뒤 승인"
    assert w.ledger.count() == 0


def test_주문_취소는_9장처럼_요청한_고객_본인이_확인한다(w):
    orders = AuthorizedOrderTools(w.repo, w.queue, w.audit)
    action_id = orders.cancel_order(UserContext.alice(), "1001").pending_action_id
    assert not w.approval.approve(UserContext.dave(), action_id).ok, "직원이 고객 대신 취소 확인"
    assert w.approval.approve(UserContext.alice(), action_id).ok
    assert w.repo.find("1001").status == OrderStatus.CANCELLED


def test_금액_형식은_원_단위_양의_정수만():
    assert ToolArgValidator.valid_amount("5000")
    assert not ToolArgValidator.valid_amount("0")
    assert not ToolArgValidator.valid_amount("-1")
    assert not ToolArgValidator.valid_amount("5,000")
    assert not ToolArgValidator.valid_amount("오천")
    assert not ToolArgValidator.valid_amount(None)
