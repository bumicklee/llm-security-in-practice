"""모델이 부를 수 있는 쿠폰 발급 도구(22장 종합 실습). 돈이 걸린 도구(ToolRisk.MONEY).

- 모델이 넘기는 인자는 orderId·amountKrw뿐. "누가"는 ToolRuntime의 user. 모델이 "관리자 요청"이라고 말해도 역할은 로그인 정보에서만(T5).
- 금액은 문자열로 바꿔 넘긴다. 숫자가 아닌 값도 변환 예외가 아니라 labcore 검사가 거부하게(T4).
- 수정 후에는 발급하지 않고 승인 대기열에 "제안"만 넣는다. 발급은 같은 테넌트 직원이 승인할 때(요청자 ≠ 승인자).
"""
from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from shopbot.tools.orders import _s, _user


class CouponArgs(BaseModel):
    orderId: str | int | None = Field(None, description="주문 번호(숫자 4~10자리)")
    amountKrw: str | int | float | None = Field(None, description="쿠폰 금액(원 단위 정수, 1~10000)")


def build_coupon_tools(lab):
    @tool("issueCoupon", args_schema=CouponArgs, response_format="content_and_artifact",
          description="로그인한 고객 본인 주문에 쿠폰 발급을 요청한다. 실제 발급은 직원이 승인해야 한다")
    def issue_coupon(orderId=None, amountKrw=None, runtime: ToolRuntime = None):
        order_id = _s(orderId)
        amount = None if amountKrw is None else (str(int(amountKrw)) if isinstance(amountKrw, float) and amountKrw.is_integer()
                                                 else str(amountKrw))
        r = lab.coupon_tools.issue_coupon(_user(runtime), order_id, amount)
        args = {"orderId": "null" if order_id is None else order_id, "amountKrw": "null" if amount is None else amount}
        return r.message, {"arguments": args, "status": r.status}

    return [issue_coupon]
