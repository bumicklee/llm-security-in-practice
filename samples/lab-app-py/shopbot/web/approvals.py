"""[승인] [거절] 버튼이 부르는 API(9장 9.4, 22장). LLM은 이 경로에 관여하지 않는다.

GET  /api/approvals              내가 요청한 대기 목록(고객 화면). 쿠폰 요청은 화면에서 "직원 확인 중"으로만 보인다(app.js)
GET  /api/approvals/staff        직원 화면: 내 테넌트의 쿠폰 요청(내가 요청한 것은 빠짐). 직원이 아니면 403
POST /api/approvals/{id}/approve 승인(취소 = 요청한 고객, 쿠폰 = 같은 테넌트 직원. 요청자 ≠ 승인자)
POST /api/approvals/{id}/reject  거절
"""
from fastapi import APIRouter, Depends, Response

from shopbot.security import current_user
from shopbot.state import LabState, get_lab

router = APIRouter(prefix="/api/approvals")


@router.get("")
def mine(user=Depends(current_user), lab: LabState = Depends(get_lab)):
    return [a.to_json() for a in lab.approvals.pending_for(user.user_id)]


@router.get("/staff")
def staff(user=Depends(current_user), lab: LabState = Depends(get_lab)):
    if not user.staff:
        return Response(status_code=403)
    return [a.to_json() for a in lab.approvals.pending_for_staff(user.user_id, user.tenant_id, "issueCoupon")]


@router.post("/{action_id}/approve")
def approve(action_id: str, user=Depends(current_user), lab: LabState = Depends(get_lab)):
    return lab.approval_service.approve(user, action_id).to_json()


@router.post("/{action_id}/reject")
def reject(action_id: str, user=Depends(current_user), lab: LabState = Depends(get_lab)):
    return lab.approval_service.reject(user, action_id).to_json()
