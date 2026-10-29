"""도구 권한(9장). 모델이 alice의 주문 번호를 골라도 bob의 요청으로는 취소되지 않는다.
본인 주문도 승인 전에는 상태가 바뀌지 않는다."""
from labcore.audit import AuditLog
from labcore.tools import ApprovalQueue, ApprovalService, OrderRepository, OrderStatus
from labcore.user import UserContext
from tests.attack import lab


def test_bob은_alice의_주문을_취소할_수_없다():
    repo = OrderRepository.seeded()
    tools = lab.order_tools(repo, ApprovalQueue(), AuditLog())
    tools.cancel_order(UserContext.bob(), "1001")   # 모델이 고른 인자 = alice 주문
    assert repo.find("1001").status == OrderStatus.PAID


def test_bob은_alice의_주문_상태도_볼_수_없다():
    tools = lab.order_tools(OrderRepository.seeded(), ApprovalQueue(), AuditLog())
    r = tools.get_order_status(UserContext.bob(), "1001")
    assert r.ok is False


def test_본인_주문도_승인_전에는_취소되지_않고_승인_후에만_바뀐다():
    repo = OrderRepository.seeded()
    queue = ApprovalQueue()
    audit = AuditLog()
    tools = lab.order_tools(repo, queue, audit)

    proposal = tools.cancel_order(UserContext.bob(), "2001")
    assert repo.find("2001").status == OrderStatus.PAID

    approval = ApprovalService(repo, queue, audit)
    assert approval.approve(UserContext.alice(), proposal.pending_action_id).ok is False   # 남이 승인 불가
    assert approval.approve(UserContext.bob(), proposal.pending_action_id).ok is True
    assert repo.find("2001").status == OrderStatus.CANCELLED
    assert approval.approve(UserContext.bob(), proposal.pending_action_id).ok is False     # 두 번 승인 불가
    assert approval.reject(UserContext.bob(), proposal.pending_action_id).ok is False      # 승인 뒤 거절도 불가
