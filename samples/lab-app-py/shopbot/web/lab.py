"""랩 확인용 API(127.0.0.1 전용). 권한 검사를 일부러 생략했다 — 실서비스 금지.

GET /api/lab/flags            방어 스위치 상태(화면이 textContent/innerHTML을 고를 때 사용, camelCase)
GET /api/lab/usage            내 오늘 토큰
GET /api/lab/orders/{id}      주문 상태(9장 실습에서 CANCELLED 확인). 소유권 확인 없음 — 실서비스 금지
GET /api/lab/coupons          발급된 쿠폰 장부(22장). 권한 확인 없음 — 실서비스 금지
GET /api/lab/audit/{reqId}    감사 로그(11장)
GET /api/lab/suspicious       의심 입력 기록(4.5): 요청 ID·사용자·사유·길이만, 원문 없음
"""
from fastapi import APIRouter, Depends, HTTPException

from shopbot.security import current_user
from shopbot.state import LabState, get_lab

router = APIRouter(prefix="/api/lab", dependencies=[Depends(current_user)])


@router.get("/flags")
def flags(lab: LabState = Depends(get_lab)):
    return lab.settings.defense.model_dump(by_alias=True)


@router.get("/usage")
def usage(user=Depends(current_user), lab: LabState = Depends(get_lab)):
    return {"userId": user.user_id, "tokensToday": lab.ledger.user_today(user.user_id), "globalToday": lab.ledger.global_today()}


@router.get("/orders/{order_id}")
def order(order_id: str, lab: LabState = Depends(get_lab)):
    o = lab.orders.find(order_id)
    if o is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return o.to_json()


@router.get("/coupons")
def coupons(lab: LabState = Depends(get_lab)):
    return [c.to_json() for c in lab.coupons.all()]


@router.get("/audit/{request_id}")
def audit(request_id: str, lab: LabState = Depends(get_lab)):
    return [e.to_json() for e in lab.audit.by_request_id(request_id)]


@router.get("/suspicious")
def suspicious(lab: LabState = Depends(get_lab)):
    return [{"requestId": e.request_id, "userId": e.user_id, "reason": e.reason, "length": e.length}
            for e in lab.suspicious.entries()]
