"""10장 SSRF 방어. 네트워크 코드는 포트(WebClientPort·HostResolver) 뒤에 둔다.

실제 HTTP 클라이언트(httpx2, follow_redirects=False)는 shopbot/tools/url_summary.py에 있다.
테스트는 가짜 웹·가짜 DNS를 넣어 네트워크 없이 돈다.
"""
import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urljoin, urlsplit


@dataclass(frozen=True)
class Page:
    """HTTP GET 한 번(리다이렉트를 따라가지 않음)의 결과."""
    status: int
    location: str | None
    body: str


class WebClientPort(Protocol):
    def get(self, url: str) -> Page: ...


class HostResolver(Protocol):
    """호스트 이름 → IP 문자열 목록. 모르는 이름이면 LookupError(socket.gaierror 포함)."""

    def __call__(self, host: str) -> list[str]: ...


def system_resolver(host: str) -> list[str]:
    """실제 DNS. socket.getaddrinfo 결과를 "모두" 돌려준다(하나라도 사설이면 막기 위해)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise LookupError(host) from e
    return sorted({i[4][0] for i in infos})


@dataclass(frozen=True)
class Fetched:
    ok: bool
    body_or_reason: str


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str


_BAD_URL_CHARS = set(' \t\r\n<>"{}|\\^`')


def _ip(addr: str):
    return ipaddress.ip_address(addr.split("%", 1)[0])


_NAT64_WKP = ipaddress.ip_network("64:ff9b::/96")      # RFC 6052 잘 알려진 NAT64 접두: 끝 32비트가 IPv4
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")   # RFC 8215 지역용 NAT64: 접두 길이가 망마다 달라 꺼낼 수 없다 → 막는다
_IPV4_COMPAT = ipaddress.ip_network("::/96")            # RFC 4291 IPv4 호환(폐기된 표기): ::a.b.c.d
_ULA = ipaddress.ip_network("fc00::/7")


def embedded_ipv4(a: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address] | None:
    """IPv4를 품은 IPv6 표기면 안의 IPv4 주소(들)를 돌려준다. 아니면 None.

    ipaddress 속성을 먼저 쓴다: ipv4_mapped(::ffff:a.b.c.d), sixtofour(2002::/16), teredo(2001::/32 → 서버·클라이언트 둘).
    속성이 없는 둘(NAT64 64:ff9b::/96, IPv4 호환 ::/96)은 끝 32비트를 꺼낸다.
    """
    if a.ipv4_mapped is not None:
        return [a.ipv4_mapped]
    if a.sixtofour is not None:
        return [a.sixtofour]
    if a.teredo is not None:
        return list(a.teredo)                 # (서버, 클라이언트) 둘 다 공인이어야 통과
    if a in _NAT64_WKP or (a in _IPV4_COMPAT and not (a.is_loopback or a.is_unspecified)):
        return [ipaddress.IPv4Address(int(a) & 0xFFFFFFFF)]
    return None


def is_public(addr) -> bool:
    """루프백·사설·링크로컬·CGNAT·벤치마크·멀티캐스트·예약·ULA를 막는다(IANA 특수 용도 주소 목록에서 출발).

    ipaddress의 is_private·is_global을 그대로 쓰지 않는다. 문서용 대역(203.0.113.0/24)까지 사설로 보기 때문이다.
    랩 테스트는 그 대역을 "공인 주소 예시"로 쓴다.
    IPv6가 IPv4를 품은 표기(IPv4 매핑·IPv4 호환·NAT64·6to4·Teredo)면 안의 IPv4로 다시 본다(2차 교차 검증 A10).
    """
    a = _ip(addr) if isinstance(addr, str) else addr
    if isinstance(a, ipaddress.IPv6Address):
        if a.is_loopback or a.is_unspecified or a.is_link_local or a.is_site_local or a.is_multicast:
            return False
        if a in _ULA or a in _NAT64_LOCAL:
            return False
        inner = embedded_ipv4(a)
        if inner is not None:
            return all(is_public(v4) for v4 in inner)
        return True
    b0, b1 = a.packed[0], a.packed[1]
    if b0 == 127 or b0 == 0 or b0 == 10:          # 루프백·0.0.0.0/8·사설
        return False
    if b0 == 172 and 16 <= b1 <= 31:
        return False
    if b0 == 192 and b1 == 168:
        return False
    if b0 == 169 and b1 == 254:                   # 링크로컬(클라우드 메타데이터 169.254.169.254 포함)
        return False
    if b0 == 100 and 64 <= b1 <= 127:             # 100.64.0.0/10 CGNAT
        return False
    if b0 == 198 and b1 in (18, 19):              # 198.18.0.0/15 벤치마크
        return False
    if b0 >= 224:                                 # 멀티캐스트·예약
        return False
    return True


class UrlFetchGuard:
    """SSRF 막기(10장 10.2). 순서가 중요하다.

    1) 스킴: https만  2) 사용자 정보(@) 금지, 포트 제한(기본 포트만)  3) 호스트 허용 목록(정확히 일치)
    4) DNS로 해석한 "모든" 주소가 공인 주소인지  5) 리다이렉트마다 1~4를 다시(GuardedUrlFetcher)
    남는 위험: 검사 뒤 DNS가 바뀌는 경우(DNS 리바인딩). 해석한 IP로 직접 연결하거나 프록시에서 한 번 더 막는다.
    """

    def __init__(self, allowed_hosts, allowed_schemes, resolver: Callable[[str], list[str]]):
        self.allowed_hosts = frozenset(allowed_hosts)
        self.allowed_schemes = frozenset(allowed_schemes)
        self.resolver = resolver

    def check(self, url: str) -> Verdict:
        url = (url or "").strip()
        if not url or any(c in _BAD_URL_CHARS for c in url):
            return Verdict(False, "BAD_URL")
        try:
            u = urlsplit(url)
            port = u.port
        except ValueError:
            return Verdict(False, "BAD_URL")
        if (u.scheme or "").lower() not in self.allowed_schemes:
            return Verdict(False, "SCHEME")
        if "@" in u.netloc:
            return Verdict(False, "USERINFO")
        if port is not None:
            return Verdict(False, "PORT")
        host = u.hostname
        if not host:
            return Verdict(False, "NO_HOST")
        if host not in self.allowed_hosts:
            return Verdict(False, "HOST_NOT_ALLOWED")
        try:
            addrs = self.resolver(host)
        except (LookupError, OSError):
            return Verdict(False, "DNS")
        if not addrs:
            return Verdict(False, "DNS")
        for a in addrs:
            try:
                if not is_public(a):
                    return Verdict(False, "PRIVATE_ADDRESS")
            except ValueError:
                return Verdict(False, "DNS")
        return Verdict(True, "ok")


def _resolve(current: str, location: str) -> str:
    """상대 경로 Location(/new)은 현재 URL 기준으로 바꾼다. 바뀐 주소도 다시 검사된다."""
    try:
        return urljoin(current, location)
    except ValueError:
        return location


class NaiveUrlFetcher:
    """[수정 전] 받은 URL을 그대로 부르고 리다이렉트도 따라간다 → 내부 관리 페이지(127.0.0.1:8081)를 읽는다(10장 10.1)."""

    def __init__(self, web: WebClientPort):
        self.web = web

    def fetch(self, url: str) -> Fetched:
        current = url
        for _ in range(5):
            p = self.web.get(current)
            if p.status // 100 == 3 and p.location is not None:
                current = _resolve(current, p.location)
                continue
            return Fetched(p.status == 200, p.body)
        return Fetched(False, "too many redirects")


class GuardedUrlFetcher:
    """[수정 후] 매 단계(처음 + 리다이렉트마다) UrlFetchGuard로 다시 검사. 리다이렉트는 최대 3번. 본문은 20,000자까지."""
    BLOCKED = "허용되지 않은 주소입니다"
    MAX_REDIRECTS = 3
    MAX_BODY = 20_000

    def __init__(self, guard: UrlFetchGuard, web: WebClientPort):
        self.guard = guard
        self.web = web

    def fetch(self, url: str) -> Fetched:
        current = url
        for _ in range(self.MAX_REDIRECTS + 1):
            v = self.guard.check(current)
            if not v.allowed:
                return Fetched(False, f"{self.BLOCKED} ({v.reason})")
            p = self.web.get(current)
            if p.status // 100 == 3 and p.location is not None:
                current = _resolve(current, p.location)
                continue
            if p.status != 200:
                return Fetched(False, f"HTTP {p.status}")
            body = p.body or ""
            return Fetched(True, body[:self.MAX_BODY])
        return Fetched(False, f"{self.BLOCKED} (TOO_MANY_REDIRECTS)")
