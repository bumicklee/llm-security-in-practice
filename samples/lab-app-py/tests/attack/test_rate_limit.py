"""요금 폭탄(7~8장). 한 사용자가 1분 안에 50번 보내면 10번까지만 모델에 닿고 나머지는 429."""
from labcore.cost import UsageLedger
from labcore.llm import ScriptedFakeLlm
from labcore.user import UserContext
from tests.attack import lab


def test_반복_호출은_429로_막히고_모델_호출_수가_한도를_넘지_않는다():
    llm = ScriptedFakeLlm()
    gw = lab.gateway(llm, UsageLedger())
    rejected = sum(1 for i in range(50) if gw.handle(UserContext.bob(), f"배송 문의 {i}").status == 429)
    assert llm.call_count <= 10
    assert rejected >= 40


def test_한_사용자가_막혀도_다른_사용자는_통과한다():
    llm = ScriptedFakeLlm()
    gw = lab.gateway(llm, UsageLedger())
    for i in range(30):
        gw.handle(UserContext.bob(), f"문의 {i}")
    assert gw.handle(UserContext.alice(), "배송 언제 와요?").status == 200
