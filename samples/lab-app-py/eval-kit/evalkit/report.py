"""출시 판단 보고서(Markdown·HTML) 만들기.

목적: 리드가 묻는 한 가지 "출시해도 되나?"에 첫 줄로 답한다.
      판단(가능·조건부·불가) → 이유 3줄 → 유형별 통과율 → 지난 배포 대비 변화 → 수용한 위험 → 실패 상세.
대응 장: 2장(2.6 첫 보고서), 13장(출시 판단 보고서), 부록 C
안전: 공격 유형 시험 문제의 입력 문구는 싣지 않는다(id·유형만). 비공개 입력 사례는 응답 발췌도 뺀다.
"""
import html
from collections import OrderedDict

DECISION = {"green": "출시 가능", "yellow": "조건부 출시", "red": "출시 불가"}
BLOCKER_KO = {"app": "앱", "approval": "승인 대기(사람 확인)", "not_found": "앱(주문 없음)", None: "앱"}
STATUS_KO = {"pass": "통과", "fail": "실패", "hold": "보류", "not_run": "미실행"}
CAT_KO = OrderedDict([
    ("injection", "지시 무시·역할 바꾸기"), ("leak-system", "시스템 프롬프트 유출"),
    ("leak-pii", "개인정보·다른 사용자 데이터"), ("benign", "정상 질문(과잉 거절)"),
    ("indirect", "간접 인젝션(문서 속 지시)"), ("tool", "금지 도구 호출"),
    ("authz", "권한(다른 사용자로 도구)"), ("tenant", "다른 테넌트 문서(LLM08)"), ("multiturn", "여러 턴 대화"),
])


def by_category(cases):
    rows = OrderedDict()
    for cat in CAT_KO:
        cs = [c for c in cases if c["category"] == cat]
        if not cs:
            continue
        passes = sum(c["passes"] for c in cs)
        judged = sum(c["passes"] + c["fails"] for c in cs)
        rows[cat] = {
            "label": CAT_KO[cat], "cases": len(cs),
            "case_pass": sum(c["status"] == "pass" for c in cs),
            "case_fail": sum(c["status"] == "fail" for c in cs),
            "case_hold": sum(c["status"] in ("hold", "not_run") for c in cs),
            "attempt_rate": (passes / judged) if judged else None,
        }
    return rows


def compare(current, baseline):
    if not baseline:
        return None
    prev = {c["id"]: c for c in baseline["cases"]}
    changes = {"worse": [], "better": [], "new_fail": [], "new_case": [], "removed": []}
    for c in current["cases"]:
        p = prev.get(c["id"])
        if p is None:
            changes["new_case"].append(c["id"])
            if c["status"] == "fail":
                changes["new_fail"].append(c["id"])
            continue
        if p["status"] == "pass" and c["status"] == "fail":
            changes["new_fail"].append(c["id"])
        if c["pass_rate"] is not None and p["pass_rate"] is not None:
            if c["pass_rate"] < p["pass_rate"] - 1e-9:
                changes["worse"].append(c["id"])
            elif c["pass_rate"] > p["pass_rate"] + 1e-9:
                changes["better"].append(c["id"])
    ids = {c["id"] for c in current["cases"]}
    changes["removed"] = [i for i in prev if i not in ids]
    changes["baseline_run"] = baseline["meta"]["run_id"]
    changes["baseline_prompt"] = baseline["meta"].get("prompt_version")
    return changes


def reasons(results, changes):
    gate = results["gate"]
    cases = {c["id"]: c for c in results["cases"]}
    out = []
    if gate["red"]:
        cats = sorted({CAT_KO[cases[i]["category"]] for i in gate["red"]})
        out.append(f"막는 실패 {len(gate['red'])}건: {', '.join(cats)} ({', '.join(gate['red'][:6])})")
    else:
        out.append("막는 실패(유출·권한·금지 도구 등) 없음")
    if gate["yellow"]:
        out.append(f"경고 {len(gate['yellow'])}건: {', '.join(gate['yellow'][:6])}")
    else:
        out.append("경고 없음")
    if changes:
        out.append(f"지난 실행({changes['baseline_run']}) 대비: 나빠짐 {len(changes['worse'])}건, "
                   f"좋아짐 {len(changes['better'])}건, 새 실패 {len(changes['new_fail'])}건")
    elif gate["accepted"]:
        out.append(f"수용한 위험 {len(gate['accepted'])}건 적용: {', '.join(gate['accepted'])}")
    else:
        out.append("비교할 지난 실행 없음(--compare로 지정)")
    return out[:3]


def _pct(v):
    return "-" if v is None else f"{v:.0%}"


def to_markdown(results, baseline=None):
    m, gate = results["meta"], results["gate"]
    changes = compare(results, baseline)
    cases = results["cases"]
    lines = [
        f"# 출시 판단 보고서 — {m['target']}",
        "",
        f"**판단: {DECISION[gate['color']]}** ({gate['color'].upper()})",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(reasons(results, changes), 1)]
    lines += [
        "",
        "## 실행 정보",
        "",
        "| 항목 | 값 |", "| --- | --- |",
        f"| 실행 | {m['run_id']} ({m['started_at']}) |",
        f"| 대상 | {m['base_url']} |",
        f"| 모델 / 프롬프트 버전 | {m.get('model')} / {m.get('prompt_version')} |",
        f"| 묶음 / 반복 | {m['suite']} / {m.get('repeats_override') or '심각도별 기본값'} |",
        f"| 채점관 | {m['judge']} |",
        f"| 커밋 | {m['git_sha']} |",
        f"| 시험 문제 | {len(cases)}개 (통과 {sum(c['status']=='pass' for c in cases)}, "
        f"실패 {sum(c['status']=='fail' for c in cases)}, 보류 {sum(c['status'] in ('hold','not_run') for c in cases)}) |",
    ]
    if results.get("budget_hit"):
        lines.append(f"| 한도 | **{results['budget_hit']}에서 멈춤** |")
    lines += ["", "## 유형별 결과", "",
              "| 유형 | 문제 수 | 통과 | 실패 | 보류 | 시도 통과율 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in by_category(cases).values():
        lines.append(f"| {row['label']} | {row['cases']} | {row['case_pass']} | {row['case_fail']} | "
                     f"{row['case_hold']} | {_pct(row['attempt_rate'])} |")
    if changes:
        lines += ["", f"## 지난 실행 대비 ({changes['baseline_run']}, 프롬프트 {changes['baseline_prompt']})", "",
                  "| 변화 | 시험 문제 |", "| --- | --- |",
                  f"| 새 실패 | {', '.join(changes['new_fail']) or '-'} |",
                  f"| 나빠짐 | {', '.join(changes['worse']) or '-'} |",
                  f"| 좋아짐 | {', '.join(changes['better']) or '-'} |",
                  f"| 새 시험 문제 | {', '.join(changes['new_case']) or '-'} |",
                  f"| 빠진 시험 문제 | {', '.join(changes['removed']) or '-'} |"]
    risks = [c for c in cases if c.get("accepted_risk")]
    lines += ["", "## 수용한 위험", ""]
    if risks:
        lines += ["| 시험 문제 | 상태 | 이유 | 승인 | 기한 |", "| --- | --- | --- | --- | --- |"]
        for c in risks:
            r = c["accepted_risk"]
            state = "**기한 지남 — 적용 안 됨**" if r.get("expired") else STATUS_KO[c["status"]]
            lines.append(f"| {c['id']} | {state} | {r.get('reason','')} | {r.get('owner','')} | {r.get('expires','')} |")
    else:
        lines.append("없음")
    blocked = [c for c in cases if c.get("app_blocked")]
    if blocked:
        lines += ["", "## 앱이 막은 도구 호출 (모델은 넘어갔음)", "",
                  "통과했지만 모델이 다른 고객 주문에 도구를 불렀고 앱의 소유자 확인이 막은 경우다. 앱 방어를 끄면 실패로 바뀐다.", "",
                  "| 시험 문제 | 앱이 막은 시도 | 결과 |", "| --- | --- | --- |"]
        for c in blocked:
            lines.append(f"| {c['id']} | {c['app_blocked']}/{c['n']} | {STATUS_KO[c['status']]} |")
    failed = [c for c in cases if c["status"] != "pass"]
    lines += ["", "## 실패·보류 상세", ""]
    if not failed:
        lines.append("없음")
    for c in failed:
        lines.append(f"### {c['id']} · {STATUS_KO[c['status']]} · {c['title']}")
        lines.append("")
        lines.append(f"- 유형/심각도/게이트: {CAT_KO[c['category']]} / {c['severity']} / {c['gate']}"
                     f" · OWASP {', '.join(c['owasp']) or '-'}")
        lines.append(f"- 통과: {c['passes']}/{c['n']} (통과율 {_pct(c['pass_rate'])}, 기준 {c['min_pass_rate']:.0%})"
                     f" · 입력: {'공개 질문 — ' + c['input_shown'] if c['input_shown'] else '자리표시/비공개(문구 생략)'}")
        s = c.get("sample")
        if s:
            for r in s["reasons"]:
                lines.append(f"- 판정: {r}")
            lines.append(f"- 응답 발췌(반복 {s['repeat']}): {s['reply_excerpt']}")
            if s["tool_calls"]:
                calls = ", ".join(f"{t.get('name')}({(t.get('args') or {}).get('order_id','')})"
                                  f"{'' if t.get('allowed') else ' → ' + BLOCKER_KO.get(t.get('blocked_by'), str(t.get('blocked_by'))) + '이 막음'}"
                                  for t in s["tool_calls"])
                lines.append(f"- 도구 기록: {calls}")
        lines.append("")
    if any(c["judge_skipped"] for c in cases):
        lines += ["> 참고: 채점관이 꺼져 있어 일부 시험은 규칙 판정만 했습니다(--judge-mode).", ""]
    lines += ["---", "모든 데이터는 가짜입니다. 공격 유형 입력 문구는 이 보고서에 싣지 않습니다."]
    return "\n".join(lines) + "\n"


def to_html(markdown_text, color):
    """의존성 없이 Markdown 보고서를 단순 HTML로 바꾼다(표·제목·목록만)."""
    bar = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}[color]
    out, in_table, in_list = [], False, False
    for line in markdown_text.splitlines():
        esc = html.escape(line)
        esc = _bold(esc)
        if line.startswith("|"):
            cells = [x.strip() for x in line.strip("|").split("|")]
            if all(set(c) <= set("- ") for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{_bold(html.escape(c))}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_bold(html.escape(c))}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{esc[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            out.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("&gt; "):
            out.append(f"<blockquote>{esc[5:]}</blockquote>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{esc}</p>")
    if in_table:
        out.append("</table>")
    if in_list:
        out.append("</ul>")
    style = ("body{font-family:sans-serif;max-width:900px;margin:2rem auto;line-height:1.5}"
             f".bar{{height:10px;background:{bar};border-radius:5px}}"
             "table{border-collapse:collapse;margin:.5rem 0}td,th{border:1px solid #ccc;padding:.3rem .6rem}"
             "th{background:#f3f4f6}blockquote{color:#555;border-left:4px solid #ddd;margin:0;padding-left:1rem}")
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>출시 판단 보고서</title>"
            f"<style>{style}</style></head><body><div class='bar'></div>" + "\n".join(out) + "</body></html>\n")


def _bold(text):
    parts = text.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))
