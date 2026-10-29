"""실행기: 시험 문제를 여러 번 돌리고, 판정하고, 통과율·기준선·게이트 색을 정한다.

목적: '한 번 통과'가 아니라 'N번 중 몇 번'으로 본다. 막을 실패(빨강)와 경고(노랑)를 나눈다.
대응 장: 8장(8.1 판정 순서), 10장(반복·통과율·기준선), 12장(게이트·한도), 13장(수용한 위험)
판정 순서: 규칙 판정 → 하나라도 실패면 그 시도는 실패(채점관 안 부름) → 규칙 모두 통과면 채점관.
"""
import datetime as _dt
import os
import time

from .judge import Judge
from .rules import RULES
from .target import TargetError

ALWAYS = [{"type": "http_ok"}]


def _today():
    return _dt.date.today().isoformat()


def accepted_risk_for(case_id, risks, today=None):
    today = today or _today()
    for r in risks or []:
        if r.get("case_id") == case_id:
            if str(r.get("expires", "9999-12-31")) >= today:
                return {**r, "expired": False}
            return {**r, "expired": True}
    return None


def grade_attempt(case, response, target_cfg, judge, endpoint_cfg=None):
    # 한도 응답(기본 429: 레이트 리밋·토큰 예산)은 막은 것도 뚫린 것도 아니다 → 그 시도는 보류(설계 5.3, LLM10은 JUnit이 증명)
    if response["status"] in (target_cfg.get("hold_statuses") or [429]):
        return "hold", [{"grader": "http_ok", "verdict": "hold",
                         "detail": f"HTTP {response['status']} — 한도에 걸려 판정 보류(레이트 리밋·토큰 예산)"}]
    ctx = {"case": case, "target": target_cfg, "session": response.get("session")}
    results = []
    graders = (ALWAYS + list(target_cfg.get("global_graders") or [])
               + list((endpoint_cfg or {}).get("graders") or []) + list(case["graders"]))
    rule_failed = False
    judge_specs = []
    for g in graders:
        if g["type"] == "llm_judge":
            judge_specs.append(g)
            continue
        verdict, detail = RULES[g["type"]](g, response, ctx)
        results.append({"grader": g["type"], "verdict": verdict, "detail": detail})
        if verdict == "fail":
            rule_failed = True
    if rule_failed:
        return "fail", results
    final = "pass"
    for g in judge_specs:
        j = judge.grade(g["rubric"], case, response["reply"])
        results.append({"grader": f"llm_judge:{g['rubric']}", "verdict": j["verdict"],
                        "detail": j.get("reason", ""), "evidence": j.get("evidence", "")})
        if j["verdict"] == "fail":
            final = "fail"
        elif j["verdict"] == "hold" and final == "pass":
            final = "hold"
    return final, results


def repeats_for(case, thresholds, suite, override):
    if override:
        return override
    if case.get("repeat"):
        return case["repeat"]
    sev = (thresholds.get("severity") or {}).get(case["severity"], {})
    return int(sev.get(f"repeats_{suite or 'full'}", 1))


def run_cases(cases, target, thresholds, judge=None, suite=None, repeats=None,
              accepted_risks=None, progress=print, today=None):
    judge = judge or Judge("off")
    budget = thresholds.get("budget") or {}
    max_requests = int(budget.get("max_requests", 5000))
    max_seconds = float(budget.get("max_minutes", 60)) * 60
    started = time.monotonic()
    out = []
    budget_hit = None
    for case in cases:
        n = repeats_for(case, thresholds, suite, repeats)
        attempts = []
        fixtures = bool((case.get("setup") or {}).get("fixtures"))
        ep = target.endpoint(case)
        # 서버가 대화를 기억하는 대상의 여러 턴 시험은 반복마다 처음부터(설계 5.4-3). reset은 시험용 문서도 지운다
        per_repeat = target.reset_each_repeat or target.uses_server_memory(case)
        try:
            target.reset()
            if fixtures:
                target.set_fixtures(True)
            for i in range(n):
                if per_repeat and i > 0:
                    target.reset()
                    if fixtures:
                        target.set_fixtures(True)
                if target.requests_made >= max_requests:
                    budget_hit = f"요청 수 한도 {max_requests}회"
                    break
                if time.monotonic() - started > max_seconds:
                    budget_hit = f"시간 한도 {budget.get('max_minutes')}분"
                    break
                response = target.send(case, i)
                verdict, results = grade_attempt(case, response, target.config, judge, ep)
                attempts.append({"repeat": i, "verdict": verdict, "results": results,
                                 "reply": response["reply"], "tool_calls": response["tool_calls"],
                                 "latency_ms": response["latency_ms"], "request_id": response.get("request_id")})
        finally:
            if (case.get("setup") or {}).get("fixtures"):
                try:
                    target.set_fixtures(False)
                except TargetError:
                    pass
        out.append(summarize_case(case, attempts, thresholds, accepted_risks, today))
        progress(_line(out[-1]))
        if budget_hit:
            break
    return out, budget_hit


def summarize_case(case, attempts, thresholds, accepted_risks, today=None):
    passes = sum(a["verdict"] == "pass" for a in attempts)
    fails = sum(a["verdict"] == "fail" for a in attempts)
    holds = sum(a["verdict"] == "hold" for a in attempts)
    judged = passes + fails
    rate = (passes / judged) if judged else None
    sev = (thresholds.get("severity") or {}).get(case["severity"], {})
    min_rate = float(sev.get("min_pass_rate", 1.0))
    max_hold = float(thresholds.get("max_hold_ratio", 0.2))
    if not attempts:
        status = "not_run"
    elif rate is None or (holds / len(attempts)) > max_hold:
        status = "hold"
    elif rate + 1e-9 >= min_rate:
        status = "pass"
    else:
        status = "fail"
    gate = case.get("gate") or (thresholds.get("gate_by_category") or {}).get(case["category"], "block")
    risk = accepted_risk_for(case["id"], accepted_risks, today)
    app_blocked = sum(any(t.get("blocked_by") == "app" for t in a["tool_calls"]) for a in attempts)
    judge_skipped = any(r["verdict"] == "skip" for a in attempts for r in a["results"])
    first_fail = next((a for a in attempts if a["verdict"] in ("fail", "hold")), None)
    sample = None
    if first_fail:
        reasons = [f"{r['grader']}: {r['detail']}" for r in first_fail["results"] if r["verdict"] in ("fail", "hold")]
        excerpt = first_fail["reply"][:200]
        if case["_input_source"] == "private":
            excerpt = "[비공개 입력 사례 — 응답 발췌는 공개 보고서에 싣지 않음]"
        sample = {"repeat": first_fail["repeat"], "reasons": reasons, "reply_excerpt": excerpt,
                  "tool_calls": first_fail["tool_calls"], "request_id": first_fail.get("request_id")}
    return {
        "id": case["id"], "title": case["title"], "category": case["category"],
        "severity": case["severity"], "owasp": case.get("owasp", []), "gate": gate,
        "suites": case["suites"], "input_source": case["_input_source"],
        "input_shown": None if case.get("input_ref") else case["input"],
        "n": len(attempts), "passes": passes, "fails": fails, "holds": holds,
        "pass_rate": None if rate is None else round(rate, 3), "min_pass_rate": min_rate,
        "status": status, "judge_skipped": judge_skipped, "app_blocked": app_blocked,
        "accepted_risk": risk, "sample": sample,
        "avg_latency_ms": int(sum(a["latency_ms"] for a in attempts) / len(attempts)) if attempts else None,
    }


def _line(c):
    mark = {"pass": "통과", "fail": "실패", "hold": "보류", "not_run": "미실행"}[c["status"]]
    rate = "-" if c["pass_rate"] is None else f"{c['pass_rate']:.0%}"
    return f"  {c['id']:<12} {mark:<3} {c['passes']}/{c['n']} ({rate}) [{c['category']}·{c['severity']}] {c['title']}"


def gate_decision(case_results, budget_hit=None):
    red, yellow, accepted = [], [], []
    for c in case_results:
        if c["status"] in ("pass",):
            continue
        risk = c.get("accepted_risk")
        if risk and not risk.get("expired"):
            accepted.append(c["id"])
            continue
        if c["status"] == "fail" and c["gate"] == "block":
            red.append(c["id"])
        else:
            yellow.append(c["id"])
    if budget_hit:
        yellow.append(f"한도 도달: {budget_hit}")
    color = "red" if red else ("yellow" if yellow else "green")
    return {"color": color, "red": red, "yellow": yellow, "accepted": accepted}


def run_meta(target, health, judge, suite, repeats, cases_paths, today=None):
    return {
        "run_id": _dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "target": target.name, "base_url": target.base_url,
        "model": health.get("model") or target.config.get("model_label"), "prompt_version": health.get("prompt_version"),
        "bot_mode": health.get("mode"), "app_authz": health.get("app_authz"),
        "temperature": health.get("temperature"),
        "judge": judge.describe(), "suite": suite or "all", "repeats_override": repeats,
        "cases_paths": [str(p) for p in cases_paths],
        "git_sha": os.environ.get("GITHUB_SHA", "local"),
        "kit_version": "1.1.0",
        "today": today or _today(),
    }
