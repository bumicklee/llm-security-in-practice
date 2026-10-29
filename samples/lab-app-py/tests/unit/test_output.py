"""11장 출력·마스킹·보관 기간 단위 테스트."""
from datetime import datetime, timedelta, timezone

from labcore.output import ConversationStore, HtmlOutputEscaper, PiiMasker, PromptLogPolicy

masker = PiiMasker()


def test_마스킹():
    assert masker.mask("연락처 010-1234-5678") == "연락처 010-****-5678"
    assert masker.mask("alice@example.com") == "a****@example.com"
    assert masker.mask("키 sk-test-FAKE-0000") == "키 sk-****"


def test_이스케이프와_허용_마크다운():
    assert HtmlOutputEscaper.escape('<b onclick="x">') == "&lt;b onclick=&quot;x&quot;&gt;"
    assert HtmlOutputEscaper.render_limited_markdown("**배송 중**\n내일 도착") == "<strong>배송 중</strong><br>내일 도착"


def test_프롬프트_로그는_해시_길이_마스킹본():
    line = PromptLogPolicy.safe("번호 010-1234-5678", masker)
    assert line.startswith("promptSha256=") and "len=" in line and "010-****-5678" in line


def test_보관_기간이_지나면_지운다():
    now = [datetime(2026, 10, 1, tzinfo=timezone.utc)]
    store = ConversationStore(lambda: now[0], masker)
    store.save("alice", "제 번호 010-1234-5678")
    assert "010-****-5678" in store.all()[0].masked_text
    now[0] = now[0] + timedelta(days=31)
    store.save("alice", "새 질문")
    assert store.purge_older_than(timedelta(days=30)) == 1
    assert len(store.all()) == 1
