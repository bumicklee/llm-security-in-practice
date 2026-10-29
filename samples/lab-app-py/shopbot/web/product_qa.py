"""상품 Q&A(RAG)와 리뷰 등록(5~6장).

POST /api/products/ask {"question"} → {answer, citedIds}     근거가 없으면 "확인할 수 없습니다"
POST /api/reviews      {"text"}     → 수집 검사기에 걸리면 저장하지 않고 검토 대기(202)
GET  /api/reviews/pending           → 검토 대기 목록(같은 테넌트 직원만, 아니면 403)
POST /api/products/ask-advisor      → 방법 B(필터 문자열) 비교용. 근거 검사 없음. 경로 이름은 HTTP 계약으로 고정
"""
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from labcore.audit import RequestIds
from shopbot.agent.schemas import AskRequest, GroundedAnswer, ReviewRequest
from shopbot.rag.ingestion import ingest_review
from shopbot.security import current_user
from shopbot.state import LabState, get_chat_model, get_lab
from shopbot.web.errors import InputRejected
from shopbot.web.rate_limit import rate_limited_user

router = APIRouter()


def guard_question(req: AskRequest, user=Depends(rate_limited_user), lab: LabState = Depends(get_lab)):
    if lab.settings.defense.input_guard:
        r = lab.input_guard.check(req.question)
        if r.suspicious:
            lab.suspicious.record(RequestIds.current(), user.user_id, r.reason, len(req.question or ""))
        if not r.allowed:
            raise InputRejected(r.reason)
    return user


@router.post("/api/products/ask", response_model=GroundedAnswer)
def ask(req: AskRequest, user=Depends(guard_question), lab: LabState = Depends(get_lab), model=Depends(get_chat_model)):
    a = lab.rag.ask(user, req.question, model)
    return {"answer": a.answer, "citedIds": list(a.cited_ids)}


@router.post("/api/products/ask-advisor")
def ask_advisor(req: AskRequest, user=Depends(guard_question), lab: LabState = Depends(get_lab),
                model=Depends(get_chat_model)):
    return {"answer": lab.rag.ask_with_advisor(user, req.question, model), "note": "방법 B: 근거 검사 없음(비교용)"}


@router.post("/api/reviews")
def review(req: ReviewRequest, user=Depends(current_user), lab: LabState = Depends(get_lab)):
    status, body = ingest_review(lab, user, req.text)
    return JSONResponse(status_code=status, content=body)


@router.get("/api/reviews/pending")
def pending(user=Depends(current_user), lab: LabState = Depends(get_lab)):
    if not user.staff:
        return Response(status_code=403)
    return [p for p in lab.pending_reviews if p["tenantId"] == user.tenant_id]
