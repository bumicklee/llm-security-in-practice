"""10장 SSRF 검사 단위 테스트(네트워크 없이 가짜 DNS).

IPv4를 품은 IPv6 표기(IPv4 매핑·IPv4 호환·NAT64·6to4·Teredo)는 안의 IPv4로 다시 본다(2차 교차 검증 A10).
주소는 모두 자리표시다: 안에 든 IPv4는 루프백 127.0.0.1·사설 10.0.0.5/192.168.0.7, 공인 예시는 문서용 203.0.113.10.
테스트 개수(1~21장 49개)는 그대로 두려고 같은 테스트 함수 안에 단언을 더했다.
"""
from labcore.ssrf import UrlFetchGuard, is_public

# 가짜 DNS: 허용 목록 호스트 → 해석 결과. v6-* 는 IPv4를 품은 IPv6 표기 하나씩
DNS = {
    "docs.shop.example": ["203.0.113.10"],
    "bad.shop.example": ["203.0.113.10", "192.168.0.7"],
    "v6.shop.example": ["::ffff:127.0.0.1"],             # IPv4 매핑(ipv4_mapped)
    "v6-compat.shop.example": ["::7f00:1"],              # IPv4 호환(::127.0.0.1, 폐기된 표기)
    "v6-nat64.shop.example": ["64:ff9b::a00:5"],         # NAT64 64:ff9b::/96 → 10.0.0.5
    "v6-nat64-local.shop.example": ["64:ff9b:1::7f00:1"],  # 지역용 NAT64 64:ff9b:1::/48 → 꺼낼 수 없으니 막음
    "v6-6to4.shop.example": ["2002:c0a8:7::"],           # 6to4 2002::/16(sixtofour) → 192.168.0.7
    "v6-teredo.shop.example": ["2001:0:cb00:710a::80ff:fffe"],  # Teredo 2001::/32(teredo) → 서버 203.0.113.10, 클라이언트 127.0.0.1
    "v6-6to4-public.shop.example": ["2002:cb00:710a::"],  # 6to4 안이 공인 예시(203.0.113.10) → 통과
}


def fake_dns(host):
    if host not in DNS:
        raise LookupError(host)
    return DNS[host]


guard = UrlFetchGuard(set(DNS), {"https"}, fake_dns)


def test_검사_순서별_차단_사유():
    assert guard.check("https://docs.shop.example/a").allowed
    assert guard.check("http://docs.shop.example/a").reason == "SCHEME"
    assert guard.check("file:///etc/hosts").reason == "SCHEME"
    assert guard.check("https://user@docs.shop.example/").reason == "USERINFO"
    assert guard.check("https://docs.shop.example:8081/").reason == "PORT"
    assert guard.check("https://127.0.0.1/admin").reason == "HOST_NOT_ALLOWED"
    assert guard.check("https://bad.shop.example/").reason == "PRIVATE_ADDRESS"   # 하나라도 사설이면 차단
    assert guard.check("https://v6.shop.example/").reason == "PRIVATE_ADDRESS"    # IPv4 매핑 루프백
    # IPv4를 품은 다른 IPv6 표기도 안의 IPv4로 다시 본다(방어 확인: 모두 거부)
    for host in ("v6-compat", "v6-nat64", "v6-nat64-local", "v6-6to4", "v6-teredo"):
        v = guard.check(f"https://{host}.shop.example/")
        assert (v.allowed, v.reason) == (False, "PRIVATE_ADDRESS"), host
    # 안의 IPv4가 공인이면 통과한다(표기만으로 막지 않는다)
    assert guard.check("https://v6-6to4-public.shop.example/").allowed
    # is_public 직접: 루프백·미지정·NAT64 안의 공인 예시
    assert not is_public("::1") and not is_public("::")
    assert is_public("64:ff9b::cb00:710a")
