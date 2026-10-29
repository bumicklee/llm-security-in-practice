"""eval 프로필이 평가 연결에 필요한 것만 더하는지 확인한다.

reset·fixtures가 200, 127.0.0.1 밖에서 오면 403 / 채팅 응답에 trace.request_id·trace.tool_calls /
시험용 리뷰도 정상 수집 경로를 지나 수정 후에는 검토 대기(REVIEW_PENDING). 기본 프로필에 끝점이 없다는 것은 test_shopbot_security가 본다.
"""
from labcore.tools import OrderStatus
from tests.app.conftest import auth, make_client


def test_reset은_200이고_주문_상태를_시드로_되돌린다(eval_bot):
    c, _, lab = eval_bot
    lab.orders.save(lab.orders.find("1001").with_status(OrderStatus.CANCELLED))
    r = c.post("/api/lab/eval/reset", auth=auth("alice"))
    assert r.status_code == 200 and r.json()["reset"] is True
    assert lab.orders.find("1001").status == OrderStatus.PAID


def test_루프백이_아니면_403():
    c, _, _ = make_client("eval", client_host="10.0.0.5")
    with c:
        assert c.post("/api/lab/eval/reset", auth=auth("alice")).status_code == 403


def test_시험용_리뷰는_수집_검사기를_지나_검토_대기가_된다(eval_bot):
    c, _, _ = eval_bot
    r = c.post("/api/lab/eval/fixtures", auth=auth("alice"), json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["fixtures"][0]["status"] == "REVIEW_PENDING"
    assert c.post("/api/lab/eval/fixtures", auth=auth("alice"), json={"enabled": False}).status_code == 200


def test_채팅_응답에_trace가_붙는다(eval_bot):
    c, _, _ = eval_bot
    r = c.post("/api/chat", auth=auth("bob"), json={"message": "배송 문의"})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert body["trace"]["request_id"]
    assert isinstance(body["trace"]["tool_calls"], list)
