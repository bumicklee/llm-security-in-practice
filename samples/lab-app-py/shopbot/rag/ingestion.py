"""리뷰 수집의 유일한 길(5장 5.3). eval 프로필의 시험용 리뷰(fixtures)도 이 함수를 지난다.

수집 검사기(IngestionScanner)에 걸리면 저장하지 않고 검토 대기(202). 검토 대기열은 랩 단순화로 메모리(실서비스는 DB + 담당자 화면).
"""
import uuid

from labcore.rag import KnowledgeDoc, TrustLevel, Visibility
from shopbot.rag.store import to_document


def ingest_review(lab, user, text: str) -> tuple[int, dict]:
    doc = KnowledgeDoc("review-" + str(uuid.uuid4())[:6], user.tenant_id, Visibility.PUBLIC,
                       "review:" + user.user_id, TrustLevel.CUSTOMER, text or "")
    findings = lab.scanner.scan(doc) if lab.settings.defense.rag_guard else []
    if findings:
        f = [x.to_json() for x in findings]
        lab.pending_reviews.append({"id": doc.id, "tenantId": user.tenant_id, "author": user.user_id, "findings": f})
        return 202, {"id": doc.id, "status": "REVIEW_PENDING", "findings": f}
    lab.vector_store.add_documents([to_document(doc)])
    return 200, {"id": doc.id, "status": "STORED"}
