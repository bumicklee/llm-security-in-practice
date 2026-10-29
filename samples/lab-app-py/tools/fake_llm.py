"""OpenAI 호환 형식으로 답하는 "가짜 LLM 서버"(2장 2.3). API 요금 0원, 매번 같은 답.

공격 자리 표시([ATTACK-xx])를 보면 일부러 "넘어간" 답을 돌려준다 → 우리 코드가 막는지 본다.
표준 라이브러리만 쓴다. 실행: python -I tools/fake_llm.py            (127.0.0.1:8070)
      BIND=0.0.0.0 python -I tools/fake_llm.py   (컨테이너 안에서만. compose가 호스트 쪽을 127.0.0.1로 묶음)
끝점:
  POST /v1/chat/completions  OpenAI Chat Completions 흉내. /chat/completions 도 같은 처리
  GET  /v1/models            모델 목록(fake-shop-model)
  GET  /usage                누적 요청·토큰(요금 대시보드가 읽음)
  POST /lab/fail?count=N     다음 N개 요청을 503으로(7장 재시도 폭주 실습)
  POST /lab/reset            누적값 초기화(흔들림 모드의 난수도 FAKE_LLM_SEED로 다시 시작)
  GET  /lab/config           흔들림 모드 설정(wobble·seed) 확인
공격 범주 규칙(attack-registry.yaml 범주와 같음):
  INJ·LEAK → 시스템 프롬프트를 읊는다      RAG → 문서 속 지시를 따라 랩 밖 가짜 링크를 추천
  OUT      → 답에 표지 태그를 섞는다       COST → 아주 긴 답
  PII      → (도구 있으면) 주문 번호로 getOrderStatus   TOOL·AUTHZ → (도구 있으면) 주문 번호로 cancelOrder
  MT       → 앞 사용자 턴에 [ATTACK-MT-가 있고 이번이 세 번째 이상 사용자 턴이면 시스템 프롬프트를 읊는다
  TENANT   → 검색 문서 블록이 있으면 첫 문서 본문을 그대로 인용
  쿠폰 도구 → 요청 tools에 issueCoupon이 있고 "쿠폰"을 말하면 issueCoupon 호출(14장 종합 실습용)
응답 형식(설계 2.5):
  ① response_format {type: json_schema} 요청에는 스키마에 맞는 JSON 본문으로 답한다(with_structured_output·ProviderStrategy)
  ② tools가 있으면 OpenAI 형식의 tool_calls로 답한다
  ③ stream: true 는 400으로 거절한다(랩은 스트리밍을 쓰지 않는다)
흔들림 모드: FAKE_LLM_WOBBLE=<0~1> 이면 공격 규칙이 그 확률로만 "넘어간다". FAKE_LLM_SEED=<정수>(기본 7).
  Python random 수열이라 같은 씨앗이면 같은 순서가 나온다.
토큰 규칙(가짜): 글자 3개 = 1토큰. 요청 보기: LOG_PROMPTS=1 이면 받은 메시지를 역할별로 표준 출력에 찍는다
  (11장 11.2 "모델 쪽에는 무엇이 도착하나" 확인용. 랩 가짜 값만 다룰 것).
"""
import json
import os
import random
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

COMPETITOR_LINK = "http://127.0.0.1:9999/fake"
HTML_PLACEHOLDER = '<mark data-lab-attack="ATTACK-OUT-01">ATTACK-OUT-01</mark>'


def parse_wobble(v):
    if v is None or not v.strip():
        return -1.0   # 흔들림 모드 꺼짐 = 공격 규칙이 항상 넘어감(결정적)
    d = float(v)
    if d < 0 or d > 1:
        raise ValueError("FAKE_LLM_WOBBLE은 0~1")
    return d


WOBBLE = parse_wobble(os.environ.get("FAKE_LLM_WOBBLE"))
SEED = int(os.environ.get("FAKE_LLM_SEED", "7"))


class State:
    lock = threading.Lock()
    requests = 0
    prompt_tokens = 0
    completion_tokens = 0
    fail_next = 0
    per_second = []          # [[epochSecond, tokens], ...] 최근 300초
    rng = random.Random(SEED)

    @classmethod
    def reset(cls):
        with cls.lock:
            cls.requests = cls.prompt_tokens = cls.completion_tokens = 0
            cls.per_second = []
            cls.rng = random.Random(SEED)


def falls():
    """공격 규칙이 이번에 "넘어갈지". 흔들림 모드가 꺼져 있으면 항상 True."""
    if WOBBLE < 0:
        return True
    with State.lock:
        return State.rng.random() < WOBBLE


def tokens(t):
    return 0 if not t else (len(t) + 2) // 3


def esc(v):
    """JSON 문자열 이스케이프(출력 바이트를 tools/_golden 녹화 답과 맞춘다)."""
    out = []
    for c in v:
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 0x20:
            out.append("\\u%04x" % ord(c))
        else:
            out.append(c)
    return "".join(out)


def content_text(c):
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):   # [{type:text, text:...}]
        return "".join(str(p["text"]) for p in c if isinstance(p, dict) and p.get("text") is not None)
    return str(c)


def strip_format_instructions(s):
    """사용자 메시지 뒤에 붙은 JSON 형식 지시(일부 프레임워크가 붙이는 글)는 규칙 판단에서 뺀다."""
    for marker in ("Your response should be in JSON format", "Here is the JSON Schema", "```json"):
        i = s.find(marker)
        if i >= 0:
            s = s[:i]
    return s


def usage_json(pt, ct):
    return f'"usage":{{"prompt_tokens":{pt},"completion_tokens":{ct},"total_tokens":{pt + ct}}}'


def record(pt, ct):
    now = int(time.time())
    with State.lock:
        State.prompt_tokens += pt
        State.completion_tokens += ct
        if State.per_second and State.per_second[-1][0] == now:
            State.per_second[-1][1] += pt + ct
        else:
            State.per_second.append([now, pt + ct])
        while len(State.per_second) > 300:
            State.per_second.pop(0)


def _int_or_none(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return int(v)


def _schema_of(req):
    """response_format {type: json_schema, json_schema: {name, schema}} 이면 스키마 dict, 아니면 None."""
    rf = req.get("response_format")
    if isinstance(rf, dict) and rf.get("type") == "json_schema":
        js = rf.get("json_schema") or {}
        schema = js.get("schema") if isinstance(js, dict) else None
        return schema if isinstance(schema, dict) else {}
    return None


_WS = "[ \t\n\x0b\f\r]"   # ASCII 공백만


def chat_reply(req):
    """요청 본문(dict) → (상태 코드, 응답 본문 문자열). 카운터(requests)는 호출한 쪽에서 올린다."""
    messages = req.get("messages") or []
    tools_v = req.get("tools")
    has_tools = isinstance(tools_v, list) and len(tools_v) > 0
    has_coupon_tool = has_tools and "issueCoupon" in json.dumps(tools_v, ensure_ascii=False)
    max_tokens = _int_or_none(req.get("max_tokens"))
    if max_tokens is None:
        max_tokens = _int_or_none(req.get("max_completion_tokens")) or 0
    schema = _schema_of(req)

    all_parts, user_turns = [], []
    system = last_user = last_role = last_tool_content = last_tool_name = last_tool_args = ""
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = "null" if m.get("role") is None else str(m.get("role"))
        calls = m.get("tool_calls")
        if isinstance(calls, list) and calls and isinstance(calls[-1], dict) and isinstance(calls[-1].get("function"), dict):
            fn = calls[-1]["function"]
            last_tool_name = "null" if fn.get("name") is None else str(fn.get("name"))
            last_tool_args = "null" if fn.get("arguments") is None else str(fn.get("arguments"))
        content = content_text(m.get("content"))
        all_parts.append(content + "\n")
        if role == "system":
            system += content
        if role == "user":
            last_user = content
            user_turns.append(content)
        if role == "tool":
            # 도구 결과가 JSON 문자열("\"...\"")로 오면 따옴표 한 겹을 벗긴다(가짜 규칙)
            t = content.strip()
            if len(t) >= 2 and t.startswith('"') and t.endswith('"'):
                try:
                    unq = json.loads(t)
                    if isinstance(unq, str):
                        t = unq
                except ValueError:
                    pass
            last_tool_content = t
        last_role = role
    all_text = "".join(all_parts)
    if os.environ.get("LOG_PROMPTS") == "1":
        for m in messages:
            if isinstance(m, dict):
                print(f"[fake-llm] {m.get('role')}: " + content_text(m.get("content")).replace("\n", " ⏎ "), flush=True)
    last_user = strip_format_instructions(last_user)

    with State.lock:
        req_no = State.requests

    # 1) 도구 호출 흉내(9장·10장)
    if has_tools and last_role == "user":
        id_m = re.search(r"([0-9]{4,10})", last_user)
        url_m = re.search(r"(https?://[^" + _WS[1:-1] + "\"']+)", last_user)
        call = args_json = None
        tool_attack = "[ATTACK-TOOL-" in last_user or "[ATTACK-AUTHZ-" in last_user
        pii_attack = "[ATTACK-PII-" in last_user
        if has_coupon_tool and "쿠폰" in last_user:
            amt = re.search(r"([0-9]{3,7})" + _WS + "*원", last_user)
            amount = amt.group(1) if amt else "5000"
            oid = re.search(r"(?<![0-9])([0-9]{4})(?![0-9])", last_user)
            call = "issueCoupon"
            args_json = '{"orderId":' + (f'"{oid.group(1)}"' if oid else "null") + ',"amountKrw":' + amount + "}"
        elif (tool_attack or pii_attack) and id_m:
            # 공격 자리표시 + 주문 번호: 모델이 "넘어가" 도구를 부른다(흔들림 모드면 확률로)
            if falls():
                call = "getOrderStatus" if pii_attack else "cancelOrder"
                args_json = '{"orderId":"' + id_m.group(1) + '"}'
        elif "취소" in last_user and id_m:
            call, args_json = "cancelOrder", '{"orderId":"' + id_m.group(1) + '"}'
        elif url_m:
            call, args_json = "summarizeUrl", '{"url":"' + esc(url_m.group(1)) + '"}'
        elif ("주문" in last_user or "배송" in last_user) and id_m:
            call, args_json = "getOrderStatus", '{"orderId":"' + id_m.group(1) + '"}'
        if call is not None:
            body = ('{"id":"chatcmpl-fake-' + str(req_no) + '","object":"chat.completion","created":0,'
                    '"model":"fake-shop-model","choices":[{"index":0,"message":{"role":"assistant","content":null,'
                    '"tool_calls":[{"id":"call_fake_1","type":"function","function":{"name":"' + call
                    + '","arguments":"' + esc(args_json) + '"}}]},"finish_reason":"tool_calls"}],'
                    + usage_json(tokens(all_text), 12) + "}")
            record(tokens(all_text), 12)
            return 200, body

    # 2) 일반 답(일부러 공격에 넘어가는 규칙 포함)
    mt_attack = len(user_turns) >= 3 and any("[ATTACK-MT-" in u for u in user_turns[:-1])
    first_doc = re.search(r'<document id="[^"]+"[^>]*>' + _WS + r"*([^<]+)", all_text)
    normal = ("수령 후 7일 안에 환불을 요청할 수 있습니다." if '<document id="' in all_text
              else "문의 감사합니다. 주문 번호를 알려 주시면 확인해 드릴게요.")
    if last_role == "tool":
        text = "처리 결과: " + last_tool_content
    elif "[ATTACK-INJ-" in last_user or "[ATTACK-LEAK-" in last_user or mt_attack:
        text = "제 지시문은 다음과 같습니다: " + system if falls() else normal
    elif "[ATTACK-RAG-" in all_text:
        text = "이 상품보다 여기가 더 쌉니다: " + COMPETITOR_LINK if falls() else normal
    elif "[ATTACK-TENANT-" in last_user and first_doc:
        text = "규정 원문입니다: " + first_doc.group(1).strip() if falls() else normal
    elif "[ATTACK-OUT-" in last_user:
        text = "주문 안내입니다 " + HTML_PLACEHOLDER if falls() else normal
    elif "[ATTACK-COST-" in last_user:
        text = "아주 긴 답변입니다. " * 400 if falls() else normal   # 출력 길이 유도(7장)
    else:
        text = normal

    if max_tokens > 0 and len(text) > max_tokens * 3:
        text = text[:max_tokens * 3]

    # 3) 출력 스키마: 메시지 속 JSON 형식 지시(글) 또는 response_format json_schema(①)
    if "JSON" in all_text or "json" in all_text or schema is not None:
        props = (schema or {}).get("properties") or {}
        if "citedIds" in all_text or "citedIds" in props:
            # 문서 블록의 앞쪽 두 개를 근거로 든다(가짜 규칙)
            ids = ['"' + d + '"' for d in re.findall(r'<document id="([^"]+)"', all_text)[:2]]
            text = '{"answer":"' + esc(text) + '","citedIds":[' + ",".join(ids) + "]}"
        else:
            # 마지막 도구 호출로 의도를 정한다(가짜 규칙): cancelOrder → CANCEL_REQUEST, getOrderStatus → ORDER_STATUS
            intent = ("CANCEL_REQUEST" if last_role == "tool" and last_tool_name == "cancelOrder"
                      else "ORDER_STATUS" if last_role == "tool" and last_tool_name == "getOrderStatus" else "PRODUCT_QA")
            oid = re.search(r'"orderId"' + _WS + "*:" + _WS + r'*"([0-9]{4,10})"', last_tool_args)
            order_id = f'"{oid.group(1)}"' if last_role == "tool" and oid else "null"
            text = '{"intent":"' + intent + '","orderId":' + order_id + ',"answer":"' + esc(text) + '"}'
    pt, ct = tokens(all_text), tokens(text)
    record(pt, ct)
    body = ('{"id":"chatcmpl-fake-' + str(req_no) + '","object":"chat.completion","created":0,'
            '"model":"fake-shop-model","choices":[{"index":0,"message":{"role":"assistant","content":"'
            + esc(text) + '"},"finish_reason":"stop"}],' + usage_json(pt, ct) + "}")
    return 200, body


def usage_body():
    with State.lock:
        hist = ",".join(f"[{s},{t}]" for s, t in State.per_second)
        return (f'{{"requests":{State.requests},"promptTokens":{State.prompt_tokens},'
                f'"completionTokens":{State.completion_tokens},"perSecond":[{hist}]}}')


def handle(method, raw_path, body_bytes):
    """(상태, 본문) — HTTP 서버와 대조 시험이 함께 쓴다. 경로는 가장 긴 접두사로 고른다."""
    u = urlsplit(raw_path)
    path, query = u.path, u.query
    contexts = ["/v1/chat/completions", "/chat/completions", "/v1/models", "/usage", "/lab/fail", "/lab/reset", "/lab/config"]
    ctx = max((c for c in contexts if path.startswith(c)), key=len, default=None)
    if ctx in ("/v1/chat/completions", "/chat/completions"):
        if method != "POST":
            return 405, '{"error":"POST only"}'
        with State.lock:
            State.requests += 1
            failing = State.fail_next > 0
            if failing:
                State.fail_next -= 1
        if failing:
            return 503, '{"error":{"message":"fake overload","type":"server_error"}}'
        try:
            req = json.loads(body_bytes.decode("utf-8") or "{}")
        except ValueError:
            return 400, '{"error":{"message":"bad json","type":"invalid_request_error"}}'
        if not isinstance(req, dict):
            req = {}
        if req.get("stream") is True:   # ③
            return 400, '{"error":{"message":"stream not supported by fake LLM","type":"invalid_request_error"}}'
        return chat_reply(req)
    if ctx == "/v1/models":
        return 200, '{"object":"list","data":[{"id":"fake-shop-model","object":"model","owned_by":"lab"}]}'
    if ctx == "/usage":
        return 200, usage_body()
    if ctx == "/lab/fail":
        if method != "POST":
            return 405, '{"error":"POST only"}'
        n = int(query[6:]) if query.startswith("count=") else 1
        with State.lock:
            State.fail_next = n
        return 200, '{"failNext":' + str(n) + "}"
    if ctx == "/lab/reset":
        if method != "POST":
            return 405, '{"error":"POST only"}'
        State.reset()
        return 200, '{"reset":true}'
    if ctx == "/lab/config":
        return 200, '{"wobble":' + ("null" if WOBBLE < 0 else repr(WOBBLE)) + ',"seed":' + str(SEED) + "}"
    return 404, "<h1>404 Not Found</h1>No context found for request"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "fake-llm"
    sys_version = ""

    def _serve(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n) if n > 0 else b""
        status, body = handle(self.command, self.path, data)
        b = body.encode("utf-8")
        self.send_response(status)
        ctype = "text/html" if status == 404 else "application/json"
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    do_GET = do_POST = do_PUT = do_DELETE = _serve

    def log_message(self, *args):   # 요청마다 줄을 찍지 않는다(LOG_PROMPTS로만 본다)
        pass


def main():
    bind = os.environ.get("BIND", "127.0.0.1")
    port = int(os.environ.get("FAKE_LLM_PORT", "8070"))
    srv = ThreadingHTTPServer((bind, port), Handler)
    srv.daemon_threads = True
    extra = "" if WOBBLE < 0 else f" · 흔들림 모드 wobble={WOBBLE} seed={SEED}"
    print(f"[fake-llm] listening on http://{bind}:{port} (가짜 응답·가짜 토큰){extra}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
