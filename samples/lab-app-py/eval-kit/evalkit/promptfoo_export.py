"""우리 시험 문제 YAML → promptfoo 설정으로 옮기기.

목적: "promptfoo 쓰면 되지 않나?"(18장, 수업 11-5·11-6)에 정면으로 답한다.
      시험 문제·판정 기준은 우리가 정한 것이고, 실행기는 바꿀 수 있다는 것을 보여 준다.
대응 장: 18장(수업 11-5·11-6) · 05 A 리뷰 F1·F2·F7
고정 버전: promptfoo 0.125.1(npm, 2026-10-25, Node.js 22.22.0 이상). 실행: npx promptfoo@0.125.1 eval -c <생성 파일>
  (녹화 직전에 한 번 더 올린다. 최신은 @latest — 화면이 달라질 수 있다)
채점 모델(F1): llm-rubric은 채점 모델을 정하지 않으면 그 PC의 API 키로 외부 기본 채점 모델을 고른다(답이 밖으로 나감).
  그래서 생성 파일에 defaultTest.options.provider = openai:chat:<JUDGE_MODEL> + apiBaseUrl <JUDGE_BASE_URL>(기본 LM Studio 127.0.0.1:1234)을 넣는다.
  JUDGE_BASE_URL이 127.0.0.1이 아니면 변환을 거부한다. 값은 변환할 때의 환경 변수로 채운다.
기준표(F2): llm-rubric value에는 판정 기준만 넣는다. 기준표의 출력 형식 줄("출력은 JSON 하나: {verdict…}")·evidence 지시는 뺀다
  (promptfoo는 자기 채점 프롬프트의 pass·score·reason을 읽는다). hold는 promptfoo에 대응 값이 없어 '옮기지 못함'으로 적는다.
변환 규칙(promptfoo 0.125.1 문서 대조 2026-10-27, 실제 실행은 【작성자 실측】):
  contains_any        → javascript (여러 값 중 하나라도)
  not_contains_any    → not-contains (값마다 하나)
  canary_absent       → not-contains (표식마다 하나)
  regex_absent        → not-regex
  regex_present       → regex
  not_refusal         → not-regex (거절 문구 패턴)
  is_refusal          → regex
  pii_format_absent / no_foreign_pii / no_url_outside_allowlist / no_unauthorized_promise
                      → javascript (같은 정규식·값 목록을 코드로)
  llm_judge           → llm-rubric (기준표 본문을 그대로)
  tool_* / no_unauthorized_tool_success
                      → 옮기지 않음: HTTP 제공자의 transformResponse가 답 문자열만 꺼내므로
                        도구 기록 판정은 이 키트에 남긴다(보고서에 '변환 안 됨'으로 표시)
안전: 자리표시 입력은 자리표시 그대로 옮긴다. 비공개 입력은 옮기지 않는다.
"""
import base64
import json
import os
import urllib.parse

from . import mini_yaml
from .rules import EMAIL_RE, PHONE_RE, PROMISE_RE, REFUSAL_RE, URL_RE

NOT_PORTABLE = {"tool_called", "tool_not_called", "no_unauthorized_tool_success", "http_ok", "response_schema",
                "no_foreign_tenant_doc"}
PROMPTFOO_VERSION = "0.125.1"
DEFAULT_JUDGE_BASE_URL = "http://127.0.0.1:1234/v1"   # LM Studio(16장)
DEFAULT_JUDGE_MODEL = "local-judge-model"             # LM Studio 화면의 모델 이름으로 바꾼다(JUDGE_MODEL)
# 기준표 system에서 promptfoo로 옮기지 않는 줄(F2): 출력 형식·근거 지시·hold 기준
_RUBRIC_DROP = ("출력은 JSON", "evidence", "- hold:")


def rubric_criteria(system_text):
    """기준표 system → llm-rubric value(판정 기준만)."""
    return "\n".join(l for l in system_text.splitlines() if l.strip() and not any(k in l for k in _RUBRIC_DROP)).strip()


def judge_provider(env=None):
    env = os.environ if env is None else env
    base = env.get("JUDGE_BASE_URL") or DEFAULT_JUDGE_BASE_URL
    if urllib.parse.urlparse(base).hostname != "127.0.0.1":
        raise ValueError(f"JUDGE_BASE_URL {base} 는 127.0.0.1이 아닙니다. 채점 모델도 내 PC의 로컬 모델만 씁니다")
    return {"id": f"openai:chat:{env.get('JUDGE_MODEL') or DEFAULT_JUDGE_MODEL}",
            "config": {"apiBaseUrl": base, "apiKey": "sk-test-FAKE-0000", "temperature": 0}}


def _js_list(values):
    return json.dumps(values, ensure_ascii=False)


def convert_grader(g, target, rubrics, case):
    t = g["type"]
    if t == "contains_any":
        return [{"type": "javascript", "value": f"{_js_list(g['values'])}.some(v => output.includes(v))"}]
    if t == "not_contains_any":
        return [{"type": "not-contains", "value": v} for v in g["values"]]
    if t == "canary_absent":
        vals = list(target.get("canaries") or []) + list(g.get("values") or [])
        if g.get("include_secrets", True):
            vals += list(target.get("secrets") or [])
        return [{"type": "not-contains", "value": v} for v in vals]
    if t == "regex_absent":
        return [{"type": "not-regex", "value": g["pattern"]}]
    if t == "regex_present":
        return [{"type": "regex", "value": g["pattern"]}]
    if t == "not_refusal":
        return [{"type": "not-regex", "value": REFUSAL_RE.pattern}]
    if t == "is_refusal":
        return [{"type": "regex", "value": REFUSAL_RE.pattern}]
    if t == "no_unauthorized_promise":
        return [{"type": "not-regex", "value": PROMISE_RE.pattern}]
    if t == "no_url_outside_allowlist":
        allow = _js_list(list(target.get("url_allowlist") or []))
        url_pat = URL_RE.pattern.replace("/", "\\/")
        # promptfoo 문서: 한 줄 단언은 const 선언 뒤 '마지막 식'이 자동으로 반환된다(return을 쓰지 않는다)
        js = (f"const allow={allow}; "
              f"[...output.matchAll(/{url_pat}/g)].every(m => allow.includes(m[1]))")
        return [{"type": "javascript", "value": js}]
    if t == "no_foreign_pii":
        session = case.get("_session") or case.get("session")
        vals = [v for e in target.get("pii_registry") or [] if e.get("owner_session") != session for v in e.get("values") or []]
        return [{"type": "javascript", "value": f"!{_js_list(vals)}.some(v => output.includes(v))"}]
    if t == "pii_format_absent":
        allow = list(target.get("pii_allowlist") or [])
        if g.get("allow_own", True):
            allow += [v for e in target.get("pii_registry") or [] if e.get("owner_session") == (case.get("_session") or case.get("session"))
                      for v in e.get("values") or []]
        js = (f"const allow={_js_list(allow)}; "
              f"const found=[...output.matchAll(/{PHONE_RE.pattern}/g), ...output.matchAll(/{EMAIL_RE.pattern}/g)].map(m=>m[0]); "
              "found.every(f => allow.includes(f))")
        return [{"type": "javascript", "value": js}]
    if t == "llm_judge":
        r = rubrics.get(g["rubric"])
        text = rubric_criteria(r["system"]) if r else f"(기준표 {g['rubric']} 없음)"
        return [{"type": "llm-rubric", "value": text}]
    return None


def _session_of(case, target):
    from .target import resolve_session
    return resolve_session(target, case.get("session"))


def _auth_value(target, session):
    entry = (target.get("sessions") or {}).get(session) or {}
    if entry.get("basic"):
        return "Basic " + base64.b64encode(str(entry["basic"]).encode("utf-8")).decode("ascii")
    return ""


def convert(cases, target, rubrics, chat_url=None, env=None):
    chat = target["chat"]
    url = chat_url or (target["base_url"].rstrip("/") + chat.get("path", "/chat"))
    has_sessions = bool(target.get("sessions"))
    tests, skipped = [], []
    for c in cases:
        if c["_input_source"] == "private":
            continue  # 비공개 입력은 생성 파일에 넣지 않는다
        # 한 제공자(chat)만 옮긴다. 다른 API·시험용 문서·서버 메모리 여러 턴은 이 키트에서만 판정
        why = ("endpoint:" + c["endpoint"]) if c.get("endpoint") and c["endpoint"] != "chat" else \
              "setup:fixtures" if (c.get("setup") or {}).get("fixtures") else \
              "turns(server_memory)" if c.get("turns") and chat.get("turn_mode") == "server_memory" else None
        if why:
            skipped.append({"id": c["id"], "graders": [why]})
            continue
        c = {**c, "_session": _session_of(c, target)}
        asserts, not_ported = [], []
        for g in c["graders"]:
            if g["type"] in NOT_PORTABLE:
                not_ported.append(g["type"])
                continue
            conv = convert_grader(g, target, rubrics, c)
            if conv is None:
                not_ported.append(g["type"])
            else:
                asserts.extend(conv)
        if not_ported:
            skipped.append({"id": c["id"], "graders": not_ported})
        if not asserts:
            continue
        vars_ = {"input": c["input"], "session": c["_session"]}
        if has_sessions:
            vars_["auth"] = _auth_value(target, c["_session"])
        tests.append({
            "description": f"{c['id']} {c['title']}",
            "vars": vars_,
            "assert": asserts,
            "metadata": {"category": c["category"], "severity": c["severity"]},
        })
    headers = {"Content-Type": "application/json"}
    if has_sessions:
        headers["Authorization"] = "{{auth}}"   # 세션(랩 사용자)마다 다른 HTTP Basic 값. 모두 가짜 계정
    body = {k: ("{{prompt}}" if v == "{input}" else "{{session}}" if v == "{session}" else v)
            for k, v in (chat.get("body") or {"message": "{input}"}).items() if v != "{history}"}
    config = {
        "description": f"{target.get('name', 'target')} — evalkit 시험 문제에서 생성(자동 생성 파일, 직접 고치지 말 것)",
        "prompts": ["{{input}}"],
        "providers": [{
            "id": "http",
            "config": {
                "url": url,
                "method": chat.get("method", "POST"),
                "headers": headers,
                "body": body,
                "transformResponse": "json." + chat.get("reply_field", "reply"),
            },
        }],
        "defaultTest": {"options": {"provider": judge_provider(env)}},
        "tests": tests,
    }
    return config, skipped


def write(config, skipped, path):
    header = ["# 자동 생성: python3 -m evalkit to-promptfoo  (promptfoo " + PROMPTFOO_VERSION + " 기준, Node.js 22.22.0 이상)",
              "# 실행 예: npx promptfoo@" + PROMPTFOO_VERSION + " eval -c " + str(path) + "   (최신은 @latest, 녹화 직전 다시 고정)",
              "# 채점 모델: defaultTest.options.provider(로컬 " + config["defaultTest"]["options"]["provider"]["config"]["apiBaseUrl"]
              + "). 지정하지 않으면 promptfoo가 외부 API 기본 채점 모델로 보낸다(F1)",
              "# llm-rubric: 기준표의 판정 기준만 옮겼다. hold(보류)는 promptfoo에 대응 값이 없어 옮기지 못함(F2)"]
    if skipped:
        header.append("# 옮기지 못한 판정·시험(도구 기록, 다른 API, 시험용 문서, 서버 메모리 여러 턴, hold) — evalkit에서만 판정:")
        header += [f"#   {s['id']}: {', '.join(s['graders'])}" for s in skipped]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n" + mini_yaml.dumps(config) + "\n")
