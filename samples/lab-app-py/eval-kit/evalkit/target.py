"""시험 대상 앱을 HTTP로 부르는 클라이언트.

목적: 채점기는 대상 앱을 HTTP로만 부른다 → 어떤 스택이든 대상 설정 파일만 바꾸면 된다.
대응 장: 2장(2.6 첫 시험), 6장(시험용 문서 넣고 빼기), 14장(14.2 다른 스택에 붙이기), 부록 E · 설계 5.3·5.4(shop-bot)
안전: base_url·health_url의 호스트가 정확히 127.0.0.1이 아니면 실행을 거부한다(localhost·::1도 거부, 03 B #37).
      (회사 시험 서버 등은 담당자 허락을 받은 뒤 대상 설정에 authorized_by를 적고 --allow-remote-target으로만)
shop-bot-py용 키(targets/shop-bot-py.yaml):
  sessions: {이름: {basic: "사용자:비밀번호"}}  세션마다 Authorization: Basic 헤더(가짜 계정)
  session_aliases: {sess-A-FAKE: alice}       시험 문제 속 세션 별칭 → 랩 사용자
  default_session                              시험 문제에 session이 없을 때
  health_url                                   관리 포트처럼 base_url과 다른 주소의 health(같은 루프백 검사)
  chat.turn_mode: server_memory                여러 턴 시험의 앞 사용자 턴을 같은 세션으로 차례로 보낸다(history를 본문에 넣지 않음)
  chat.request_id_header                       응답 헤더의 요청 ID를 결과에 남긴다
  tool_aliases: {앱 도구 이름: 시험 문제 도구 이름}
  trace.tool_calls의 {name, arguments, status}(EXECUTED·PROPOSED·DENIED)는 판정기가 쓰는 {name, args, allowed, blocked_by}로 바꾼다
  admin.reset_each_repeat: true                반복마다 reset(그리고 필요하면 fixtures)을 다시 부른다
                                               (turn_mode: server_memory 대상의 여러 턴 시험은 이 값과 상관없이 반복마다 reset)
  endpoints: {이름: {path, method, body, reply_field, cited_field, tool_calls_field, graders}}
                                               chat 말고 다른 API(예: 상품 Q&A RAG)를 부르는 시험용. 시험 문제의 endpoint: 이름
  sessions.<이름>.tenant                       테넌트 시험(no_foreign_tenant_doc)이 쓰는 세션의 테넌트
  tenant_docs: {테넌트: [문서 ID, …]}          다른 테넌트 문서 ID가 근거(cited_field)나 답에 나오면 실패
  tool_not_called_fails_on: executed           금지 도구 판정에서 EXECUTED(allowed)만 실패로 센다(승인 대기·앱 거부는 방어 동작)
"""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import mini_yaml

LOCAL_HOSTS = {"127.0.0.1"}   # localhost는 hosts 파일에 따라 다른 곳을 가리킬 수 있어 받지 않는다


class TargetError(RuntimeError):
    pass


def _get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _fill(template, values):
    if isinstance(template, dict):
        return {k: _fill(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill(v, values) for v in template]
    if isinstance(template, str):
        if template.startswith("{") and template.endswith("}") and template[1:-1] in values:
            return values[template[1:-1]]  # "{history}" → 목록 그대로
        out = template
        for k, v in values.items():
            if isinstance(v, str):
                out = out.replace("{" + k + "}", v)
        return out
    return template


def resolve_session(cfg, name):
    """시험 문제의 세션 이름 → 대상의 세션 이름(session_aliases). 없으면 default_session, 그것도 없으면 그대로."""
    if not name:
        return cfg.get("default_session") or "sess-A-FAKE"
    return (cfg.get("session_aliases") or {}).get(name, name)


def _check_local(url, allow_remote, authorized_by, what):
    host = urllib.parse.urlparse(url).hostname
    if host in LOCAL_HOSTS:
        return
    if allow_remote and authorized_by:
        return
    raise TargetError(
        f"{what} {url} 는 내 PC(127.0.0.1)가 아닙니다. "
        "이 키트는 내 앱만 시험합니다(localhost·::1도 받지 않음). 허락받은 시험 서버라면 대상 설정에 authorized_by를 적고 "
        "--allow-remote-target을 붙이세요.")


_STATUS = {"EXECUTED": (True, None), "PROPOSED": (False, "approval"), "DENIED": (False, "app")}


def normalize_tool_calls(calls, cfg):
    """앱마다 다른 도구 기록 모양을 판정기 모양으로 맞춘다. 원래 값(status·arguments)도 남긴다."""
    aliases = cfg.get("tool_aliases") or {}
    out = []
    for c in calls:
        if not isinstance(c, dict):
            continue
        c = dict(c)
        c["name"] = aliases.get(c.get("name"), c.get("name"))
        if "status" in c and "allowed" not in c:
            allowed, blocked_by = _STATUS.get(str(c["status"]).upper(), (False, "app"))
            c["allowed"] = allowed
            if blocked_by:
                c["blocked_by"] = blocked_by
        if "args" not in c and isinstance(c.get("arguments"), dict):
            a = dict(c["arguments"])
            if "orderId" in a and "order_id" not in a:
                a["order_id"] = a["orderId"]
            c["args"] = a
        out.append(c)
    return out


def _header(headers, name):
    for k, v in (headers or {}).items():
        if k.lower() == name.lower():
            return v
    return None


def session_tenant(cfg, session):
    entry = (cfg.get("sessions") or {}).get(session) or {}
    return entry.get("tenant")


class Target:
    def __init__(self, config, allow_remote=False):
        self.config = config
        self.name = config.get("name", "target")
        self.base_url = config["base_url"].rstrip("/")
        _check_local(self.base_url, allow_remote, config.get("authorized_by"), "대상 주소")
        if config.get("health_url"):
            _check_local(config["health_url"], allow_remote, config.get("authorized_by"), "health 주소")
        self.chat = config["chat"]
        self.sessions = config.get("sessions") or {}
        self.admin = config.get("admin") or {}
        self.timeout = float(config.get("timeout_s", 30))
        self.headers = dict(config.get("headers") or {})
        self.requests_made = 0

    @classmethod
    def from_file(cls, path, allow_remote=False):
        return cls(mini_yaml.load_file(path), allow_remote=allow_remote)

    def auth_headers(self, session=None):
        """세션 이름 → Authorization 헤더. sessions가 없는 대상(세션을 본문에 넣는 앱)은 빈 헤더."""
        if not self.sessions:
            return {}
        name = session or self.config.get("default_session")
        entry = self.sessions.get(name)
        if entry is None:
            raise TargetError(f"대상 설정 sessions에 '{name}'이 없습니다(session_aliases 확인)")
        if entry.get("basic"):
            token = base64.b64encode(str(entry["basic"]).encode("utf-8")).decode("ascii")
            return {"Authorization": "Basic " + token}
        return dict(entry.get("headers") or {})

    def _request(self, method, path, body=None, extra_headers=None, url=None, want_headers=False):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json", **self.headers, **(extra_headers or {})}
        req = urllib.request.Request(url or (self.base_url + path), data=data, headers=headers, method=method)
        resp_headers = {}
        self.requests_made += 1
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status, raw, resp_headers = resp.status, resp.read(), dict(resp.headers.items())
        except urllib.error.HTTPError as exc:
            status, raw, resp_headers = exc.code, exc.read(), dict(exc.headers.items()) if exc.headers else {}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TargetError(f"대상 앱에 연결하지 못했습니다({self.base_url}): {exc}") from None
        latency = int((time.monotonic() - start) * 1000)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"_raw_text": raw.decode("utf-8", "replace")[:2000]}
        if want_headers:
            return status, payload, latency, resp_headers
        return status, payload, latency

    def health(self):
        url = self.config.get("health_url")
        path = self.config.get("health_path")
        if not (url or path):
            return {}
        status, payload, _ = self._request("GET", path, url=url, extra_headers=self.auth_headers())
        if status != 200:
            raise TargetError(f"health 확인 실패: HTTP {status}")
        return payload

    def reset(self):
        if self.admin.get("reset_path"):
            status, payload, _ = self._request("POST", self.admin["reset_path"], {}, self.auth_headers())
            if self.sessions and status != 200:
                raise TargetError(f"reset 실패: HTTP {status} {payload}(eval 프로필·127.0.0.1 실행인지 확인)")

    def set_fixtures(self, enabled):
        path = self.admin.get("fixtures_path")
        if not path:
            raise TargetError("이 대상은 시험용 문서 넣기(admin.fixtures_path)를 지원하지 않습니다")
        status, payload, _ = self._request("POST", path, {"enabled": bool(enabled)}, self.auth_headers())
        if status != 200:
            raise TargetError(f"시험용 문서 설정 실패: HTTP {status}")
        return payload

    @property
    def reset_each_repeat(self):
        return bool(self.admin.get("reset_each_repeat"))

    def endpoint(self, case):
        """시험 문제가 부를 API 설정. endpoint가 없으면 chat. 없는 이름이면 설정 오류."""
        name = case.get("endpoint")
        if not name or name == "chat":
            return self.chat
        eps = self.config.get("endpoints") or {}
        if name not in eps:
            raise TargetError(f"대상 설정 endpoints에 '{name}'이 없습니다(시험 문제 {case['id']})")
        return {**{k: v for k, v in self.chat.items() if k in ("method", "request_id_header")}, **eps[name]}

    def uses_server_memory(self, case):
        return self.endpoint(case).get("turn_mode") == "server_memory" and bool(case.get("turns"))

    def _post_chat(self, session, text, history, case, repeat, turn=None, ep=None):
        ep = ep or self.chat
        values = {"session": session, "input": text, "history": history}
        body = _fill(ep.get("body", {"message": "{input}"}), values)
        extra = {"X-Eval-Repeat": str(repeat), "X-Eval-Case": case["id"], **self.auth_headers(session)}
        if turn is not None:
            extra["X-Eval-Turn"] = str(turn)
        return self._request(ep.get("method", "POST"), ep.get("path", "/chat"), body, extra,
                             want_headers=True)

    def send(self, case, repeat):
        session = resolve_session(self.config, case.get("session"))
        ep = self.endpoint(case)
        turns = case.get("turns", [])
        if ep.get("turn_mode") == "server_memory" and turns:
            # 서버가 대화 기록을 사용자 기준으로 기억하는 앱: 앞 사용자 턴을 같은 세션으로 차례로 보내고
            # 마지막 답만 판정한다. 시험 문제의 assistant 턴은 보내지 않는다(서버의 실제 답이 기록에 남음)
            for n, t in enumerate(x for x in turns if x.get("role") == "user"):
                st, _, _, _ = self._post_chat(session, t["content"], [], case, repeat, turn=n, ep=ep)
                if st != 200:
                    break
            history = []
        else:
            history = [{"role": t["role"], "content": t["content"]} for t in turns]
        status, payload, latency, headers = self._post_chat(session, case["input"], history, case, repeat, ep=ep)
        reply = _get_path(payload, ep.get("reply_field", "reply"))
        tool_calls = _get_path(payload, ep.get("tool_calls_field", "trace.tool_calls"))
        cited = _get_path(payload, ep["cited_field"]) if ep.get("cited_field") else None
        rid_header = ep.get("request_id_header")
        return {
            "session": session,
            "endpoint": case.get("endpoint") or "chat",
            "cited_ids": [str(x) for x in cited] if isinstance(cited, list) else [],
            "status": status,
            "reply": reply if isinstance(reply, str) else "",
            "tool_calls": normalize_tool_calls(tool_calls, self.config) if isinstance(tool_calls, list) else [],
            "trace_available": tool_calls is not None,
            "latency_ms": latency,
            "request_id": _header(headers, rid_header) if rid_header else None,
            "body": payload,
        }
