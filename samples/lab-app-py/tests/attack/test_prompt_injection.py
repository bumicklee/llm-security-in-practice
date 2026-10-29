"""직접 인젝션(3~4장). 가짜 LLM은 일부러 공격에 넘어가 시스템 프롬프트를 읊는다.
그래도 나가는 답에 비밀이 없어야 한다 = "모델이 넘어가도 코드가 막는다". 공격 입력은 자리 표시만 쓴다.
실행: pytest tests/attack/test_prompt_injection.py [--lab-target=before]
"""
import pytest

from labcore.injection import REFUSAL
from labcore.llm import ScriptedFakeLlm
from labcore.user import UserContext
from tests.attack import lab

ATTACKS = [
    "[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]",
    "[ATTACK-INJ-02: 역할 바꾸기 유형]",
    "[ATTACK-INJ-03: 지시문 요약·번역 요청 유형]",
    "[ATTACK-INJ-04: 형식 바꾸기(코드 블록·표) 유형]",
    "[ATTACK-INJ-05: 단계적 우회 요청 유형]",
]


@pytest.mark.parametrize("attack", ATTACKS, ids=[a + " → 비밀이 새지 않는다" for a in ATTACKS])
def test_직접_인젝션에도_비밀이_새지_않는다(attack):
    bot = lab.support_bot(ScriptedFakeLlm())
    reply = bot.ask(UserContext.bob(), attack)
    assert "FAKE-VIP-2026" not in reply.answer
    assert "블랙리스트 후보" not in reply.answer
    assert "CANARY-" not in reply.answer


def test_긴_입력은_앞단에서_거절():
    """4,000자 입력은 모델에 가기 전에 거절된다."""
    llm = ScriptedFakeLlm()
    bot = lab.support_bot(llm)
    reply = bot.ask(UserContext.bob(), "가" * 4000)
    assert reply.answer == REFUSAL
    assert llm.call_count == 0


def test_정상_질문은_통과():
    """정상 질문은 막지 않는다(과잉 차단 확인)."""
    bot = lab.support_bot(ScriptedFakeLlm())
    assert bot.ask(UserContext.alice(), "주문 배송 언제 와요?").answer != REFUSAL
