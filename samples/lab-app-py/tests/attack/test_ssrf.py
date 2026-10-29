"""SSRF(10장). "URL 요약" 도구가 내부 관리 페이지(랩 안 127.0.0.1:8081)를 읽지 못한다.
네트워크 없이 가짜 웹과 가짜 DNS(HostResolver 포트)로 돈다. 공인 주소 예시는 문서용 대역(203.0.113.0/24)."""
from labcore.ssrf import Page
from tests.attack import lab

ADMIN_SECRET = "FAKE-ADMIN-NOTE-0000"


class FakeWeb:
    PAGES = {
        "http://127.0.0.1:8081/admin": Page(200, None, "관리자 메모: " + ADMIN_SECRET),
        "https://docs.shop.example/guide": Page(200, None, "배송 안내 문서"),
        "https://docs.shop.example/moved": Page(302, "http://127.0.0.1:8081/admin", ""),
        "https://docs.shop.example/old": Page(301, "/guide", ""),   # 상대 경로 리다이렉트
        "https://rebind.shop.example/x": Page(200, None, "내부 메모: " + ADMIN_SECRET),
    }

    def get(self, url):
        return self.PAGES.get(url, Page(404, None, ""))


def fake_dns(host):
    table = {"docs.shop.example": ["203.0.113.10"], "rebind.shop.example": ["10.0.0.5"], "127.0.0.1": ["127.0.0.1"]}
    if host not in table:
        raise LookupError(host)
    return table[host]


def test_내부_관리_페이지를_직접_부를_수_없다():
    r = lab.url_fetcher(FakeWeb(), fake_dns).fetch("http://127.0.0.1:8081/admin")
    assert ADMIN_SECRET not in r.body_or_reason


def test_허용_도메인의_리다이렉트로_내부에_들어갈_수_없다():
    r = lab.url_fetcher(FakeWeb(), fake_dns).fetch("https://docs.shop.example/moved")
    assert ADMIN_SECRET not in r.body_or_reason


def test_허용_도메인이라도_사설_주소로_해석되면_막는다():
    r = lab.url_fetcher(FakeWeb(), fake_dns).fetch("https://rebind.shop.example/x")
    assert ADMIN_SECRET not in r.body_or_reason


def test_허용된_공개_문서는_가져온다():
    r = lab.url_fetcher(FakeWeb(), fake_dns).fetch("https://docs.shop.example/guide")
    assert r.ok
    # 같은 도메인 안의 상대 경로 리다이렉트(/guide)는 따라간다(따라간 주소도 다시 검사)
    assert lab.url_fetcher(FakeWeb(), fake_dns).fetch("https://docs.shop.example/old").ok
