"""출력·개인정보·감사 로그(11장)."""
from labcore.audit import AuditLog, RequestIds
from labcore.llm import ChatMessage, LlmRequest, ScriptedFakeLlm
from labcore.output import PiiMasker, PromptLogPolicy
from labcore.tools import ApprovalQueue, OrderRepository
from labcore.user import UserContext
from tests.attack import lab


def test_모델이_만든_HTML_태그는_화면에서_글자로만_보인다():
    model_text = ScriptedFakeLlm().call(LlmRequest([ChatMessage.user("[ATTACK-OUT-01: 답에 태그 섞기 유도 유형]")], 0)).text
    html = lab.renderer().to_html(model_text)
    assert "<mark" not in html
    assert "&lt;mark" in html


def test_프롬프트_로그에_가짜_키와_전화번호가_남지_않는다():
    prompt = "제 번호는 010-1234-5678 이고 키는 sk-test-FAKE-0000abcd 입니다"
    line = PromptLogPolicy.raw(prompt) if lab.before() else PromptLogPolicy.safe(prompt, PiiMasker())
    assert "010-1234-5678" not in line
    assert "sk-test-FAKE-0000abcd" not in line


def test_남의_주문_취소_시도를_요청_ID로_거꾸로_추적할_수_있다():
    audit = AuditLog()
    tools = lab.order_tools(OrderRepository.seeded(), ApprovalQueue(), audit)
    request_id = RequestIds.begin()
    try:
        tools.cancel_order(UserContext.bob(), "1001")
    finally:
        RequestIds.end()
    types = [e.type for e in audit.by_request_id(request_id)]
    assert "TOOL_CALL" in types and "TOOL_DENIED" in types
