# 프롬프트: URL을 받는 도구에 SSRF 방어 넣기

- **쓰는 곳:** 10장 10.1~10.2, 수업 5-5
- **도구:** Claude Code
- **목적:** URL 요약·웹 검색처럼 외부를 호출하는 도구가 내부망·루프백·메타데이터 주소에 닿지 못하게 한다.

## 프롬프트 본문

```text
{도구_파일} 의 URL 가져오기에 SSRF 방어를 넣어라.

1. 검사 클래스 {검사_클래스}(순수 Python, 표준 라이브러리 ipaddress·urllib.parse 만):
   스킴 {허용_스킴}만 → userinfo(@) 금지 → 기본 포트만 → 호스트 허용 목록 {허용_호스트} 정확히 일치
   → DNS로 해석한 "모든" 주소(socket.getaddrinfo 결과 전부)가 공인인지
     (루프백·사설·링크로컬·0.0.0.0/8·100.64/10·멀티캐스트·fc00::/7, IPv4를 품은 IPv6 표기는 안의 IPv4로 다시 판정)
2. HTTP 클라이언트는 리다이렉트를 자동으로 따라가지 않게(httpx 계열이면 follow_redirects=False). 따라갈 때마다 1번 검사를 다시. 최대 {리다이렉트}번.
3. 본문은 {최대_본문}자까지만 모델에 돌려준다. 연결 오류 글은 모델에 보내지 않는다.
4. DNS 해석기와 HTTP 클라이언트를 생성자 인자(Protocol)로 빼서 테스트에서 가짜를 쓴다(네트워크 없이).
5. pytest: 루프백 직접, 허용 도메인의 리다이렉트로 내부, 허용 도메인이 사설 IP로 해석, 정상 공개 문서 통과.
   공인 주소 예시는 문서용 대역(203.0.113.0/24)만 쓴다.
6. 남는 위험(DNS 리바인딩)을 주석으로: 해석한 IP로 직접 연결하거나 나가는 프록시에서 한 번 더 막는다.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{도구_파일}` | `shopbot/tools/url_summary.py` (`summarizeUrl`) |
| `{검사_클래스}` | `UrlFetchGuard` |
| `{허용_스킴}` | https |
| `{허용_호스트}` | docs.shop.example (`shopbot/profiles/default.yaml`의 `fetch_allowed_hosts`) |
| `{리다이렉트}` / `{최대_본문}` | 3 / 2,000 |

## 기대 출력 예

```text
check("http://127.0.0.1:8081/admin") → SCHEME
check("https://127.0.0.1/admin")     → HOST_NOT_ALLOWED
check("https://bad.shop.example/")   → PRIVATE_ADDRESS
tests/attack/test_ssrf.py 4 passed · tests/unit/test_ssrf_unit.py::test_검사_순서별_차단_사유 PASSED
```

랩 정답: `samples/lab-app-py/labcore/ssrf/__init__.py`(`UrlFetchGuard`, `GuardedUrlFetcher`, `is_public`, `system_resolver`), `shopbot/tools/url_summary.py`(`Httpx2WebClient`, `follow_redirects=False`). 실측: `_실측/5-5_ssrf-before.txt`·`5-5_ssrf-after.txt`(수정 후 답 "허용되지 않은 주소입니다 (SCHEME)").

## 주의

- 실습 대상은 랩 안의 가짜 관리 페이지(`127.0.0.1:8081/admin`)뿐이다. 클라우드 메타데이터 주소 등 실제 내부 주소로 시험하지 않는다.
- 차단 목록(블랙리스트)만으로 막는 코드가 나오면 허용 목록 방식으로 바꾸게 한다.
- 검사 순서가 바뀌면 차단 사유가 달라진다. 사유 코드를 테스트에서 함께 본다.
