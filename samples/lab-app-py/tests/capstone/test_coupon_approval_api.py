"""22장 종합 실습의 FastAPI 연결 확인. 쿠폰 도구 → 승인 대기 → 승인 API의 승인자 분리
(요청자 ≠ 승인자, 같은 테넌트 직원). 가짜 채팅 모델이라 키·네트워크 불필요. 실행: pytest -m capstone
"""
from types import SimpleNamespace

import pytest

from labcore.user import UserContext
from shopbot.agent.middleware import LabContext
from shopbot.tools.registry_check import unknown_tools
from labcore.tools import ToolAllowlist
from tests.app.conftest import auth, make_client

pytestmark = pytest.mark.capstone


def _rt(user):
    return SimpleNamespace(context=LabContext(user=user))


def test_쿠폰은_고객_본인이_아니라_같은_매장_직원만_승인한다():
    c, _, lab = make_client()
    with c:
        issue = next(t for t in lab.tools if t.name == "issueCoupon")
        answer, _ = issue.func(orderId="1001", amountKrw="5000", runtime=_rt(UserContext.alice()))
        assert "직원 승인 후 발급" in answer
        assert lab.coupons.count() == 0

        # 고객 화면 목록에는 보이지만(직원 확인 중), 고객은 승인할 수 없다
        mine = c.get("/api/approvals", auth=auth("alice"))
        assert mine.status_code == 200
        assert mine.json()[0]["toolName"] == "issueCoupon" and mine.json()[0]["amountKrw"] == 5000
        action_id = mine.json()[0]["id"]
        assert c.post(f"/api/approvals/{action_id}/approve", auth=auth("alice")).json()["ok"] is False
        assert c.get("/api/approvals/staff", auth=auth("alice")).status_code == 403

        # 다른 테넌트 직원(carol)은 목록에도 없고 승인도 못 한다
        assert c.get("/api/approvals/staff", auth=auth("carol")).json() == []
        assert c.post(f"/api/approvals/{action_id}/approve", auth=auth("carol")).json()["ok"] is False

        # 같은 테넌트 직원(dave)이 승인하면 발급
        assert len(c.get("/api/approvals/staff", auth=auth("dave")).json()) == 1
        assert c.post(f"/api/approvals/{action_id}/approve", auth=auth("dave")).json()["ok"] is True
        assert lab.coupons.issued_for("1001").approved_by == "dave"
        assert len(c.get("/api/lab/coupons", auth=auth("dave")).json()) == 1


def test_허용_목록에_없는_도구가_붙으면_시작_검사가_잡는다():
    c, _, lab = make_client()
    tools = [t for t in lab.tools if t.name in ("getOrderStatus", "cancelOrder", "issueCoupon")]
    assert unknown_tools(ToolAllowlist.lab(), set(), tools) == []
    assert unknown_tools(ToolAllowlist.lab(), {"issueCoupon"}, tools) == ["issueCoupon"]
