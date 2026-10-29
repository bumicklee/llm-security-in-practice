"""목적: run-attacks.sh 본체. 공격 유형 자리 표시를 127.0.0.1 랩 앱에만 보내고 결과 표를 찍는다.
실행: python3 -I attack-kit/run_attacks.py http://127.0.0.1:8080 attack-kit/attack-cases.json
대응 장: 4장 4.6, 12장 12.1
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PASSWORD = "FAKE-pass-0000"  # 가짜 계정 비밀번호


def require_loopback(url):
    """호스트가 정확히 127.0.0.1인 http 주소만 받는다. @(사용자 정보)·localhost·다른 IP는 거부."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "http" or "@" in u.netloc or "\\" in url or u.hostname != "127.0.0.1":
        sys.exit("거부: 대상은 http://127.0.0.1(내 PC의 랩)만 허용합니다. 받은 값: " + url)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """리다이렉트를 따라가지 않는다(랩 밖으로 나가는 길을 막음)."""
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def call(target, path, user, payload):
    req = urllib.request.Request(target + path, data=json.dumps(payload).encode("utf-8"), method="POST")
    token = base64.b64encode(f"{user}:{PASSWORD}".encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with OPENER.open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except OSError as e:
        return 0, str(e)


def get(target, path, user):
    req = urllib.request.Request(target + path)
    token = base64.b64encode(f"{user}:{PASSWORD}".encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    with OPENER.open(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def expand(text):
    if text.startswith("@REPEAT:"):
        _, ch, n = text.split(":")
        return ch * int(n)
    return text


NO_VERDICT = "none"


def judge(case, status, body, target):
    if case.get("judge") == NO_VERDICT:
        return NO_VERDICT  # 판정 없음: API 응답만으로는 막힘·뚫림을 가릴 수 없다(예: OUT-01은 브라우저 화면에서 확인). 셈에서 뺀다
    if status == 0:
        return None  # 앱에 연결하지 못함(보류). 앱이 켜져 있는지 먼저 본다. 뚫림으로 세지 않는다
    if status == 429:
        return None  # 레이트 리밋에 걸려 이 공격은 판정 못 함(보류). ATTACK_DELAY 로 간격을 두고 다시
    if "expectStatus" in case:
        return status in case["expectStatus"]
    if status == 400:
        return True  # 앞단 입력 검사에서 막힘
    for bad in case.get("mustNotContain", []):
        if bad in body:
            return False
    if "maxAnswerChars" in case:
        try:
            ans = json.loads(body).get("answer", "")
        except ValueError:
            ans = body
        if len(ans) > case["maxAnswerChars"]:
            return False
    if "checkOrder" in case:
        o = get(target, "/api/lab/orders/" + case["checkOrder"]["id"], case["user"])
        if o.get("status") != case["checkOrder"]["mustBe"]:
            return False
    return True


def reason_429(body):
    """429의 이유: RATE_LIMITED(1분 요청 수) / TOKEN_BUDGET(토큰 한도, 쌓인 대화 기록 포함). 대처가 다르다."""
    try:
        return json.loads(body).get("error", "?")
    except ValueError:
        return "?"


def main():
    target, path = sys.argv[1], sys.argv[2]
    require_loopback(target)
    cases = json.load(open(path, encoding="utf-8"))["cases"]
    delay = float(os.environ.get("ATTACK_DELAY", "0"))  # 레이트 리밋(1분 10번)을 피하려면 7 정도
    blocked = held = unjudged = 0
    print(f"{'ID':<18}{'유형':<28}{'HTTP':>5}  결과")
    for c in cases:
        key = "text" if c["endpoint"] == "/api/reviews" else ("question" if c["endpoint"] == "/api/products/ask" else "message")
        status, body = call(target, c["endpoint"], c["user"], {key: expand(c["input"])})
        ok = judge(c, status, body, target)
        if ok == NO_VERDICT:
            unjudged += 1
            label = "판정 없음(브라우저 확인)"
        elif ok is None:
            held += 1
            label = f"보류(429 {reason_429(body)})" if status == 429 else "보류(연결 실패)"
        else:
            blocked += ok
            label = "막힘" if ok else "뚫림"
        print(f"{c['id']:<18}{c['type'][:26]:<28}{status:>5}  {label}")
        if delay:
            time.sleep(delay)
    judged = len(cases) - held - unjudged
    # 용어 통일(설계 2.5): 통과(=막힘) ÷ 판정. 보류(429·연결 실패)와 판정 없음은 빼고 센다
    print(f"\n통과(=막힘) {blocked} / 판정 {judged} (보류 {held}, 판정 없음 {unjudged}, 전체 {len(cases)})")
    if held:
        print("보류가 있으면 ATTACK_DELAY=7 ./attack-kit/run-attacks.sh 로 다시 돌린다(레이트 리밋을 끄지 않고 간격만 둔다).")
        print("TOKEN_BUDGET 보류는 간격으로 풀리지 않는다(같은 사용자의 대화 기록이 쌓임). 앱을 다시 띄우거나 eval 프로필의 reset으로 비운다.")


if __name__ == "__main__":
    main()
