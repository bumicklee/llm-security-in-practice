"""7~8장 방어 부품 단위 테스트."""
from labcore.cost import (ConversationWindow, CostAlert, FakePricing, RetryAmplification, TokenBudget, UsageLedger,
                          UserRateLimiter)
from labcore.llm import ChatMessage, Usage, count_tokens
from labcore.user import UserContext


def test_가짜_단가_계산():
    assert FakePricing.krw(Usage(1000, 1000)) == 40.0
    assert count_tokens("가나다라") == 2


def test_레이트_리밋은_시간이_지나면_다시_찬다():
    now = [0]
    rl = UserRateLimiter(3, 60, clock_ns=lambda: now[0])
    for _ in range(3):
        assert rl.try_acquire("bob").allowed
    blocked = rl.try_acquire("bob")
    assert not blocked.allowed
    assert blocked.retry_after_seconds > 0
    assert rl.try_acquire("alice").allowed   # 사용자별 버킷
    now[0] += 60 * 1_000_000_000
    assert rl.try_acquire("bob").allowed


def test_토큰_한도_3단계():
    ledger = UsageLedger()
    budget = TokenBudget(TokenBudget.Limits(100, 500, 10_000, 100_000), ledger)
    assert budget.check(UserContext.bob(), 101).reason == "REQUEST_TOO_LARGE"
    ledger.add("bob", "shop-a", Usage(450, 40))
    assert budget.check(UserContext.bob(), 50).reason == "USER_DAILY_LIMIT"
    assert budget.check(UserContext.alice(), 50).allowed


def test_재시도가_겹치면_곱해진다():
    assert RetryAmplification.worst_case_calls(3) == 3       # openai SDK 기본 max_retries 2 = 시도 3번
    assert RetryAmplification.worst_case_calls(3, 3) == 9    # 앞단 3 × 기본 3
    assert RetryAmplification.worst_case_calls(3, 2) == 6    # 랩 수정 후(max_retries=1 = 시도 2번)


def test_대화_창은_최근_N개만():
    h = [ChatMessage.user(f"m{i}") for i in range(50)]
    w = ConversationWindow.last_n(h, ConversationWindow.DEFAULT_MAX_MESSAGES)
    assert len(w) == 20
    assert w[0].text == "m30"


def test_비용_경보는_비율마다_한_번씩():
    alert = CostAlert(10_000, 0.5, 0.8, 1.0)
    assert alert.evaluate(4_000) == []
    assert alert.evaluate(5_100) == ["COST_50PCT"]
    assert alert.evaluate(5_200) == []
    assert alert.evaluate(12_000) == ["COST_80PCT", "COST_100PCT"]
