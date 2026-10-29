"""토큰 "양" 막기(8장 8.2~8.3). 긴 입력은 모델에 가기 전에 막히고,
대화가 길어져도 한 요청의 입력 토큰이 끝없이 늘지 않는다(창 자르기)."""
from labcore.cost import UsageLedger
from labcore.llm import ScriptedFakeLlm
from labcore.user import UserContext
from tests.attack import lab


class RecordingLlm:
    """요청마다 입력 메시지 수를 기록하는 가짜 LLM."""

    def __init__(self):
        self.inner = ScriptedFakeLlm()
        self.message_counts: list[int] = []

    def call(self, r):
        self.message_counts.append(len(r.messages))
        return self.inner.call(r)


def test_아주_긴_입력은_모델에_닿지_않는다():
    llm = RecordingLlm()
    gw = lab.gateway(llm, UsageLedger())
    reply = gw.handle(UserContext.bob(), "가" * 30_000)
    assert reply.status in (400, 429)
    assert llm.message_counts == []


def test_대화가_길어져도_요청당_메시지_수는_창_크기를_넘지_않는다():
    llm = RecordingLlm()
    gw = lab.gateway(llm, UsageLedger())
    # 같은 사용자 30턴. 수정 전은 기록을 통째로 보내 메시지 수가 계속 는다.
    for i in range(30):
        gw.handle(UserContext.alice(), f"질문 {i}")
    # 마지막 요청은 system 1 + 창(최대 20) + user 1 = 최대 22개
    assert llm.message_counts[-1] <= 22
