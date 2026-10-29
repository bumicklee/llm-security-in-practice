"""모델이 부를 수 있는 주문 도구(9장).

- 모델이 넘기는 인자는 orderId 하나뿐. "누가" 부르는지는 runtime: ToolRuntime[LabContext]의 user(서버가 넣은 값).
  ToolRuntime 매개변수는 모델에게 보이는 도구 스키마에서 빠진다.
- 실제 판단은 labcore OrderTools(수정 전 TrustingOrderTools / 수정 후 AuthorizedOrderTools). 취소는 승인 대기열에 "제안"만.
- 인자 스키마(Pydantic args_schema)는 타입만 넉넉히 받는다(문자열·숫자·null). 형식 검사(숫자 4~10자리)는 labcore
  ToolArgValidator가 한다. 스키마에 정규식을 넣으면 검증 실패가 도구 밖에서 나서 수정 전/후 스위치로 비교할 수 없기 때문이다.
"""
from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field


class OrderIdArgs(BaseModel):
    orderId: str | int | None = Field(None, description="주문 번호(숫자 4~10자리)")


def _s(v) -> str | None:
    return None if v is None else str(v)


def _user(runtime: ToolRuntime):
    ctx = getattr(runtime, "context", None)
    if ctx is None or getattr(ctx, "user", None) is None:
        raise RuntimeError("보안 컨텍스트 없음: 도구 실행 거부")
    return ctx.user


def build_order_tools(lab):
    """앱 하나(LabState)에 묶인 도구를 만든다. 모듈 전역 상태를 쓰지 않는다."""

    @tool("getOrderStatus", args_schema=OrderIdArgs, response_format="content_and_artifact",
          description="로그인한 고객 본인의 주문 상태를 조회한다")
    def get_order_status(orderId=None, runtime: ToolRuntime = None):
        order_id = _s(orderId)
        r = lab.order_tools.get_order_status(_user(runtime), order_id)
        art = {"arguments": {"orderId": "null" if order_id is None else order_id}, "status": r.status}
        if not r.ok:
            return r.message, art
        # 주문 조회 결과에는 수령인 연락처(가짜 값)가 붙는다. 소유권 확인(9장)이 없으면 남의 연락처가 답에 섞인다(9-3)
        o = lab.orders.find(order_id)
        contact = lab.users.contact_of(o.owner_id) if o else None
        return (r.message if contact is None else f"{r.message} · 수령인 연락처 {contact}"), art

    @tool("cancelOrder", args_schema=OrderIdArgs, response_format="content_and_artifact",
          description="로그인한 고객 본인의 주문 취소를 요청한다. 실제 취소는 고객이 화면에서 승인해야 한다")
    def cancel_order(orderId=None, runtime: ToolRuntime = None):
        order_id = _s(orderId)
        r = lab.order_tools.cancel_order(_user(runtime), order_id)
        return r.message, {"arguments": {"orderId": "null" if order_id is None else order_id}, "status": r.status}

    return [get_order_status, cancel_order]
