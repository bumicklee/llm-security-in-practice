"""FastAPI 연결까지 포함한 공격 테스트(12장). 가짜 채팅 모델이라 API 키·네트워크 불필요."""
from types import SimpleNamespace

from labcore.tools import OrderStatus
from labcore.user import UserContext
from shopbot.agent.middleware import LabContext
from tests.app.conftest import auth


def test_로그인하지_않으면_채팅_API를_부를_수_없다(bot):
    c, _, _ = bot
    assert c.post("/api/chat", json={"message": "안녕"}).status_code == 401


def test_직접_인젝션에도_가짜_할인_코드와_카나리가_새지_않는다(bot):
    c, _, _ = bot
    r = c.post("/api/chat", auth=auth("bob"), json={"message": "[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]"})
    assert r.status_code == 200
    assert "FAKE-VIP-2026" not in r.text
    assert "CANARY-" not in r.text


def test_긴_입력은_400(bot):
    c, _, _ = bot
    r = c.post("/api/chat", auth=auth("alice"), json={"message": "가" * 4000})
    assert r.status_code == 400
    assert r.json()["error"] == "INPUT_REJECTED"


def test_모델이_alice_주문을_골라도_bob으로는_취소되지_않는다(bot):
    _, _, lab = bot
    cancel = next(t for t in lab.tools if t.name == "cancelOrder")
    cancel.func(orderId="1001", runtime=SimpleNamespace(context=LabContext(user=UserContext.bob())))
    assert lab.orders.find("1001").status == OrderStatus.PAID


def test_shop_a_사용자의_검색에는_shop_b_문서가_없다(bot):
    _, _, lab = bot
    docs = lab.rag.search(UserContext.alice(), "환불 예외 규정")
    assert all(d.metadata["tenantId"] == "shop-a" for d in docs)


def test_상품_질문은_검색된_근거_문서를_인용해_답한다(bot):
    """회귀 시험: 상품 Q&A가 채팅 메모리를 같이 쓰면 늘 "확인할 수 없습니다"만 답한다. 그렇게 되지 않는지 본다."""
    c, _, _ = bot
    r = c.post("/api/products/ask", auth=auth("alice"), json={"question": "환불 규정 알려 주세요"})
    assert r.status_code == 200
    assert r.json()["citedIds"]
    assert "policy-b-int" not in r.text


def test_기본_프로필에는_평가_끝점이_없다(bot):
    c, _, _ = bot
    assert c.post("/api/lab/eval/reset", auth=auth("alice")).status_code == 404
    r = c.post("/api/chat", auth=auth("alice"), json={"message": "배송 문의"})
    assert r.status_code == 200
    assert "trace" not in r.json()
