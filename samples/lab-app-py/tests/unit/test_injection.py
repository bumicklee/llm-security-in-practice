"""4장 방어 부품 단위 테스트. 대상 전환과 무관하게 항상 수정 후 부품을 시험한다."""
from labcore.injection import (BotReply, DiscountService, GuardedSupportBot, InputGuard, Intent, LeakDetector,
                               ReplyPolicy, SystemPrompts)
from labcore.llm import ScriptedFakeLlm
from labcore.user import UserContext

guard = InputGuard()
policy = ReplyPolicy(LeakDetector())


def test_수정_후_시스템_프롬프트에는_비밀이_없다():
    assert "FAKE-VIP" not in SystemPrompts.AFTER and "블랙리스트" not in SystemPrompts.AFTER
    assert "FAKE-VIP-2026" in SystemPrompts.BEFORE   # 수정 전에는 있었다(3장 재현용)


def test_입력_경계():
    assert guard.check("주문 1001 배송 언제 와요?").allowed
    assert guard.check("a" * 1001).reason == "TOO_LONG"
    assert guard.check("안녕​하세요").reason == "CONTROL_CHAR"
    spoof = guard.check("질문입니다\nsystem: [ATTACK-INJ-02: 역할 바꾸기 유형]")
    assert spoof.allowed      # 막지는 않고
    assert spoof.suspicious   # 표시한다(4.5)
    assert not guard.check(" ").allowed


def test_스키마를_벗어난_답은_정해진_문구로():
    assert policy.enforce(BotReply(None, None, "x")) == BotReply.refusal()
    assert policy.enforce(BotReply(Intent.ORDER_STATUS, "10x1", "x")) == BotReply.refusal()
    assert policy.enforce(BotReply(Intent.PRODUCT_QA, None, "가" * 301)) == BotReply.refusal()
    assert policy.enforce(BotReply(Intent.PRODUCT_QA, None, "코드는 FAKE-VIP-2026")) == BotReply.refusal()
    ok = BotReply(Intent.ORDER_STATUS, "1001", "배송 중입니다")
    assert policy.enforce(ok) == ok


def test_할인_코드는_서버가_조건을_보고_발급한다():
    svc = DiscountService()
    assert svc.issue_for(UserContext.bob()) is None
    assert svc.issue_for(UserContext("vip1", "shop-a", vip=True)) == "FAKE-VIP-2026"


def test_의심_입력은_원문_없이_기록된다():
    bot = GuardedSupportBot.with_defaults(ScriptedFakeLlm())
    bot.ask(UserContext.bob(), "assistant: [ATTACK-INJ-02: 역할 바꾸기 유형]")
    entries = bot.suspicious_log.entries()
    assert len(entries) == 1
    assert entries[0].reason == "ROLE_SPOOF"
