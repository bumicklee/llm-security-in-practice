"""시험 문제 YAML 읽기·검사·비공개 입력 덮어쓰기.

목적: 시험 문제를 '코드처럼' 다룬다. 빠진 칸은 CI에서 막고, 공격 유형의 실제 문구는
      공개 파일에 두지 않고 비공개 파일(private/attack_inputs.yaml)에서만 읽는다.
대응 장: 3장(3.2 스키마 검사, 3.3 이름·태그·심각도), 4~7장(유형별 시험 문제), 부록 A
"""
import re
from pathlib import Path

from . import mini_yaml

CATEGORIES = ("injection", "leak-system", "leak-pii", "benign", "indirect", "tool", "authz", "tenant", "multiturn")
SEVERITIES = ("critical", "high", "medium", "low")
SUITES = ("quick", "full")
GATES = ("block", "warn")
# 실제 문구가 공개 파일에 있으면 안 되는 유형: 입력은 반드시 input_ref + 자리표시
PLACEHOLDER_ONLY = ("injection", "leak-system", "multiturn")

GRADER_PARAMS = {
    "http_ok": set(),
    "response_schema": {"required"},
    "canary_absent": {"include_secrets", "values"},
    "contains_any": {"values"},
    "not_contains_any": {"values"},
    "regex_present": {"pattern"},
    "regex_absent": {"pattern"},
    "pii_format_absent": {"allow_own"},
    "no_foreign_pii": set(),
    "is_refusal": set(),
    "not_refusal": set(),
    "no_unauthorized_promise": set(),
    "no_url_outside_allowlist": set(),
    "tool_called": {"name"},
    "tool_not_called": {"names"},
    "no_unauthorized_tool_success": set(),
    "no_foreign_tenant_doc": set(),
    "llm_judge": {"rubric"},
}
REQUIRED_PARAMS = {
    "contains_any": {"values"}, "not_contains_any": {"values"}, "regex_present": {"pattern"},
    "regex_absent": {"pattern"}, "tool_called": {"name"}, "tool_not_called": {"names"},
    "llm_judge": {"rubric"}, "response_schema": {"required"},
}

ID_RE = re.compile(r"^(C-)?[A-Z]+-\d{2,3}$")   # shop-bot판은 C-<범주>-<NN>(설계 5.5), 다른 스택용 portable은 P-NN
REF_RE = re.compile(r"^ATTACK-[A-Z]+-[A-Z0-9]+(-T\d+)?$")
PLACEHOLDER_RE = re.compile(r"^\[(ATTACK-[A-Z]+-[A-Z0-9]+(?:-T\d+)?)(?::[^\]\n]*)?\]")   # 콜론형 [ATTACK-INJ-01: 유형 이름](등록부)


class CaseError(ValueError):
    pass


def validate_case(case, source="?"):
    """빠진 칸·잘못된 값을 모두 모아 목록으로 돌려준다(빈 목록이면 통과)."""
    errs = []

    def need(key, kind):
        if key not in case:
            errs.append(f"{source}: '{key}' 칸이 없습니다")
            return False
        if not isinstance(case[key], kind):
            errs.append(f"{source}: '{key}' 형식이 틀렸습니다")
            return False
        return True

    if not isinstance(case, dict):
        return [f"{source}: 파일 최상위는 매핑이어야 합니다"]
    for key in ("id", "title", "category", "severity", "intent", "input", "expected_behavior"):
        need(key, str)
    if need("graders", list) and not case["graders"]:
        errs.append(f"{source}: graders가 비어 있습니다(판정 방법 없는 시험 문제는 받지 않습니다)")
    if errs:
        return errs

    if not ID_RE.match(case["id"]):
        errs.append(f"{source}: id 형식은 'C-INJ-01'·'INJ-01'처럼 대문자-숫자입니다")
    if case["category"] not in CATEGORIES:
        errs.append(f"{source}: category는 {CATEGORIES} 중 하나")
    if case["severity"] not in SEVERITIES:
        errs.append(f"{source}: severity는 {SEVERITIES} 중 하나")
    for s in case.get("suites", ["full"]):
        if s not in SUITES:
            errs.append(f"{source}: suites 값 '{s}'는 {SUITES} 중 하나")
    if "gate" in case and case["gate"] not in GATES:
        errs.append(f"{source}: gate는 block 또는 warn")
    if "repeat" in case and (not isinstance(case["repeat"], int) or not 1 <= case["repeat"] <= 50):
        errs.append(f"{source}: repeat는 1~50 정수")

    ref = case.get("input_ref")
    m = PLACEHOLDER_RE.match(case["input"])
    if ref is not None:
        if not REF_RE.match(str(ref)):
            errs.append(f"{source}: input_ref 형식은 'ATTACK-INJ-01'")
        if not m or m.group(1) != ref:
            errs.append(f"{source}: input_ref가 있으면 input은 '[{ref}: 유형 이름] — 자리표시' 형식이어야 합니다")
    elif m:
        errs.append(f"{source}: 자리표시 input에는 input_ref가 필요합니다")
    if case["category"] in PLACEHOLDER_ONLY and ref is None:
        errs.append(f"{source}: '{case['category']}' 유형은 공개 파일에 실제 문구를 두지 않습니다. input_ref + 자리표시를 쓰세요")

    for t in case.get("turns", []) or []:
        if not isinstance(t, dict) or t.get("role") not in ("user", "assistant") or not isinstance(t.get("content"), str):
            errs.append(f"{source}: turns 항목은 {{role: user|assistant, content: 문자열}}")
            continue
        tm = PLACEHOLDER_RE.match(t["content"])
        if tm and t.get("ref") != tm.group(1):
            errs.append(f"{source}: 자리표시 turn에는 같은 값의 ref가 필요합니다")

    for g in case["graders"]:
        if not isinstance(g, dict) or "type" not in g:
            errs.append(f"{source}: grader 항목에는 type이 필요합니다")
            continue
        gtype = g["type"]
        if gtype not in GRADER_PARAMS:
            errs.append(f"{source}: 모르는 grader type '{gtype}'")
            continue
        extra = set(g) - {"type"} - GRADER_PARAMS[gtype]
        if extra:
            errs.append(f"{source}: '{gtype}'에 모르는 칸 {sorted(extra)}")
        missing = REQUIRED_PARAMS.get(gtype, set()) - set(g)
        if missing:
            errs.append(f"{source}: '{gtype}'에 필요한 칸 {sorted(missing)}")
    if "endpoint" in case and (not isinstance(case["endpoint"], str) or not re.match(r"^[a-z][a-z0-9_]*$", case["endpoint"])):
        errs.append(f"{source}: endpoint는 대상 설정 endpoints의 이름(소문자·숫자·밑줄)")
    if case.get("setup") is not None:
        setup = case["setup"]
        if not isinstance(setup, dict) or set(setup) - {"fixtures"}:
            errs.append(f"{source}: setup은 {{fixtures: true|false}}만 지원합니다")
    return errs


PORTABLE_DIR = "portable"   # 다른 스택용 시험(13-6). cases/를 통째로 줄 때는 빼고, 경로로 직접 줄 때만 읽는다
CAPSTONE_DIR = "capstone"   # 22장 종합 실습(쿠폰 도구) 시험 6개. 1~21장의 50개를 지키려고 portable처럼 경로로 줄 때만 읽는다
OPT_IN_DIRS = (PORTABLE_DIR, CAPSTONE_DIR)


def iter_case_files(paths):
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix in (".yaml", ".yml"):
            yield p
        elif p.is_dir():
            yield from sorted(x for x in p.rglob("*.y*ml") if x.suffix in (".yaml", ".yml")
                              and not any(d in OPT_IN_DIRS and d != p.name for d in x.relative_to(p).parts[:-1]))


def load_private_inputs(path):
    """비공개 입력 파일을 읽는다. 없으면 빈 dict. 값은 화면·보고서에 절대 출력하지 않는다."""
    path = Path(path)
    if not path.exists():
        return {}
    data = mini_yaml.load_file(path) or {}
    inputs = data.get("inputs") or {}
    out = {}
    for ref, entry in inputs.items():
        text = entry.get("text") if isinstance(entry, dict) else entry
        if isinstance(text, str) and text.strip() and not text.strip().startswith("<<"):
            out[ref] = text
    return out


def load_cases(paths, private_path=None, suite=None, ids=None):
    cases, errors, seen = [], [], {}
    private = load_private_inputs(private_path) if private_path else {}
    for f in iter_case_files(paths):
        try:
            case = mini_yaml.load_file(f)
        except ValueError as exc:
            errors.append(f"{f}: YAML 오류: {exc}")
            continue
        errs = validate_case(case, str(f))
        if errs:
            errors.extend(errs)
            continue
        if case["id"] in seen:
            errors.append(f"{f}: id '{case['id']}'가 {seen[case['id']]}와 겹칩니다")
            continue
        seen[case["id"]] = str(f)
        case.setdefault("suites", ["full"])
        case.setdefault("session", None)   # 없으면 대상 설정 default_session(target.resolve_session)
        case.setdefault("turns", [])
        case["_file"] = str(f)
        ref = case.get("input_ref")
        if ref and ref in private:
            case["input"] = private[ref]
            case["_input_source"] = "private"
        else:
            case["_input_source"] = "placeholder" if ref else "public"
        for t in case["turns"]:
            if t.get("ref") and t["ref"] in private:
                t["content"] = private[t["ref"]]
                case["_input_source"] = "private"
        cases.append(case)
    if suite:
        cases = [c for c in cases if suite in c["suites"]]
    if ids:
        cases = [c for c in cases if c["id"] in ids]
    return cases, errors
