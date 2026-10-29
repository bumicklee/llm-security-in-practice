"""9장 도구 인자 검증·허용 목록 단위 테스트."""
from labcore.tools import ToolAllowlist, ToolArgValidator, ToolRisk


def test_도구_인자는_사용자_입력처럼_검증한다():
    assert ToolArgValidator.valid_order_id("1001")
    assert not ToolArgValidator.valid_order_id("1001 abc")
    assert not ToolArgValidator.valid_order_id(None)
    assert not ToolArgValidator.valid_quantity(-1)
    assert ToolArgValidator.valid_quantity(3)
    assert ToolArgValidator.valid_coupon("FALL-10")
    assert not ToolArgValidator.valid_coupon("x y!")


def test_등록하지_않은_도구는_허용되지_않는다():
    allow = ToolAllowlist.lab()
    assert not allow.allowed("deleteAllOrders")
    assert allow.risk_of("cancelOrder") == ToolRisk.MONEY
