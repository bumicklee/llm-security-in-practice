"""evalkit 명령줄.

실행(eval-kit 폴더에서):
  python3 -m evalkit validate cases/                       # 스키마 검사(3장)
  python3 -m evalkit list cases/                           # 유형별 개수(3.5, 7.5)
  python3 -m evalkit run --cases cases/starter             # 첫 시험(2.6)
  python3 -m evalkit run --suite quick --gate              # PR용 빠른 묶음 + 게이트(12장)
  python3 -m evalkit report results/latest/results.json --compare results/baseline/results.json  (13장)
  python3 -m evalkit agreement judge/labels/human_labels.example.jsonl --judge-mode heuristic     (9장)
  python3 -m evalkit to-promptfoo --out promptfoo/promptfooconfig.generated.yaml                 (11장)
  python3 -m evalkit check-private                         # 비공개 입력 파일 상태(문구는 출력 안 함)
  python3 -m evalkit run --today 2100-01-01                # 수용한 위험 기한이 지난 날로 시연(13장)
기본 대상: targets/shop-bot-py.yaml(FastAPI 랩, 127.0.0.1:8080, eval 프로필). 다른 스택: --target targets/support-bot-python.yaml --cases cases/portable
종료 코드: 0 = 초록·노랑(--fail-on-yellow면 노랑도 1), 1 = 빨강, 2 = 설정·시험 문제 오류, 3 = 대상 앱 연결 실패
"""
import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from . import agreement, mini_yaml, promptfoo_export, report
from .cases import CATEGORIES, load_cases, load_private_inputs
from .judge import Judge, load_rubrics
from .runner import gate_decision, run_cases, run_meta
from .target import Target, TargetError

KIT_DIR = Path(__file__).resolve().parents[1]


def _p(path):
    """상대 경로는 현재 폴더 기준, 없으면 키트 폴더 기준으로 찾는다."""
    p = Path(path)
    return p if p.exists() or p.is_absolute() else KIT_DIR / p


def _shown(path):
    """화면에 찍을 경로. 현재 폴더 안이면 상대 경로로 바꾼다.
    첫 실행이라 results/가 아직 없어도 `results/…`로 찍힌다(홈 경로가 화면·녹화에 찍히지 않게, 4차 검토 M5)."""
    p = Path(path)
    try:
        return p.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return p


def _load_yaml(path, default=None):
    p = _p(path)
    return mini_yaml.load_file(p) if p.exists() else (default if default is not None else {})


def cmd_validate(args):
    cases, errors = load_cases([_p(x) for x in args.paths])
    for e in errors:
        print("오류:", e)
    print(f"시험 문제 {len(cases)}개 통과, 오류 {len(errors)}건")
    return 2 if errors else 0


def cmd_list(args):
    cases, errors = load_cases([_p(x) for x in args.paths], private_path=_p(args.private))
    if errors:
        for e in errors:
            print("오류:", e)
        return 2
    by_cat = Counter(c["category"] for c in cases)
    by_src = Counter(c["_input_source"] for c in cases)
    print(f"{'유형':<12} 개수")
    for cat in CATEGORIES:
        if by_cat[cat]:
            print(f"{cat:<12} {by_cat[cat]}")
    print(f"{'합계':<12} {len(cases)}")
    print(f"입력 출처: 공개 질문 {by_src['public']} · 자리표시 {by_src['placeholder']} · 비공개 {by_src['private']}")
    print(f"묶음: quick {sum('quick' in c['suites'] for c in cases)} · full {sum('full' in c['suites'] for c in cases)}")
    return 0


def cmd_check_private(args):
    path = _p(args.private)
    if not path.exists():
        try:
            shown = path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            shown = path.name
        print(f"비공개 입력 파일 없음: {shown} → 모든 공격 유형 시험은 자리표시로 돕니다(가짜 LLM·스텁 시연용).")
        return 0
    filled = load_private_inputs(path)
    cases, _ = load_cases([_p("cases")])
    refs = sorted({c["input_ref"] for c in cases if c.get("input_ref")} |
                  {t["ref"] for c in cases for t in c["turns"] if t.get("ref")})
    missing = [r for r in refs if r not in filled]
    print(f"비공개 입력: 채움 {len(refs) - len(missing)}/{len(refs)} (문구는 출력하지 않음)")
    if missing:
        print("비어 있는 항목:", ", ".join(missing))
    return 0


def cmd_run(args):
    thresholds = _load_yaml(args.thresholds)
    risks = (_load_yaml(args.accepted_risks, {}) or {}).get("risks") or []
    paths = [_p(x) for x in (args.cases or ["cases"])]
    cases, errors = load_cases(paths, private_path=_p(args.private), suite=args.suite,
                               ids=set(args.only.split(",")) if args.only else None)
    if errors:
        for e in errors:
            print("오류:", e)
        return 2
    if not cases:
        print("실행할 시험 문제가 없습니다(경로·--suite·--only 확인).")
        return 2
    target_path = _p(args.target)
    if not target_path.is_file():   # 트레이스백 대신 설정 오류로 알린다(3차 검토 B3-3)
        print(f"설정 오류: 대상 설정 파일이 없습니다: {args.target}")
        return 2
    try:
        target = Target.from_file(target_path, allow_remote=args.allow_remote_target)
        health = target.health()
    except TargetError as exc:
        print("대상 오류:", exc)
        return 3
    try:
        judge = Judge(args.judge_mode, load_rubrics(_p("judge/rubrics")))
    except ValueError as exc:
        print("설정 오류:", exc)
        return 2
    print(f"대상 {target.base_url} · 모델 {health.get('model') or target.config.get('model_label') or '-'} · "
          f"프롬프트 {health.get('prompt_version') or '-'} · "
          f"시험 문제 {len(cases)}개 · 채점관 {judge.describe()}")
    try:
        case_results, budget_hit = run_cases(cases, target, thresholds, judge, args.suite, args.repeats, risks,
                                             today=args.today)
    except TargetError as exc:
        print("대상 오류:", exc)
        return 3
    results = {"meta": run_meta(target, health, judge, args.suite, args.repeats, paths, args.today),
               "cases": case_results, "budget_hit": budget_hit,
               "requests": target.requests_made, "judge_calls": judge.calls}
    results["gate"] = gate_decision(case_results, budget_hit)
    out_dir = _p(args.out) / results["meta"]["run_id"]
    n = 2
    while out_dir.exists():  # 같은 초에 두 번 돌리면 덮어쓰지 않고 -2, -3 …을 붙인다
        out_dir = _p(args.out) / f'{results["meta"]["run_id"]}-{n}'
        n += 1
    results["meta"]["run_id"] = out_dir.name
    out_dir.mkdir(parents=True)
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    baseline = _read_results(args.compare) if args.compare else None
    md = report.to_markdown(results, baseline)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    (out_dir / "report.html").write_text(report.to_html(md, results["gate"]["color"]), encoding="utf-8")
    latest = _p(args.out) / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(out_dir, latest)
    _print_summary(results, out_dir)
    return _exit_code(results["gate"]["color"], args)


def _read_results(path):
    p = _p(path)
    if not p.exists():
        print(f"(비교 기준 없음: {_shown(p)})")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _print_summary(results, out_dir):
    cs = results["cases"]
    fails = sum(c["status"] == "fail" for c in cs)
    holds = sum(c["status"] in ("hold", "not_run") for c in cs)
    g = results["gate"]
    print(f"\n{len(cs)}개 중 {fails}개 실패, {holds}개 보류 · 요청 {results['requests']}회")
    print(f"게이트: {g['color'].upper()} — {report.DECISION[g['color']]}"
          + (f" · 막는 실패 {', '.join(g['red'])}" if g["red"] else "")
          + (f" · 경고 {', '.join(g['yellow'])}" if g["yellow"] else ""))
    print(f"보고서: {_shown(out_dir / 'report.html')}")


def _exit_code(color, args):
    if not getattr(args, "gate", False):
        return 0
    if color == "red" or (color == "yellow" and args.fail_on_yellow):
        return 1
    return 0


def cmd_report(args):
    results = _read_results(args.results)
    if results is None:
        return 2
    baseline = _read_results(args.compare) if args.compare else None
    md = report.to_markdown(results, baseline)
    out = Path(args.results).with_name("report.md")
    out.write_text(md, encoding="utf-8")
    out.with_name("report.html").write_text(report.to_html(md, results["gate"]["color"]), encoding="utf-8")
    print(md if args.print else f"보고서: {out} / {out.with_name('report.html')}")
    return 0


def cmd_agreement(args):
    rows = agreement.load_labels(_p(args.labels))
    judge = Judge(args.judge_mode, load_rubrics(_p("judge/rubrics")))
    res = agreement.measure(rows, judge)
    print(agreement.format_report(res, judge.describe()))
    return 0


def cmd_to_promptfoo(args):
    cases, errors = load_cases([_p(x) for x in (args.cases or ["cases"])])
    if errors:
        for e in errors:
            print("오류:", e)
        return 2
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only.split(","))]
    target = _load_yaml(args.target)
    try:
        config, skipped = promptfoo_export.convert(cases, target, load_rubrics(_p("judge/rubrics")))
    except ValueError as exc:
        print("설정 오류:", exc)
        return 2
    out = Path(args.out) if Path(args.out).parent.exists() else _p(args.out)   # 지금 폴더 기준 경로가 되면 그대로(화면에 절대 경로를 찍지 않게)
    promptfoo_export.write(config, skipped, out)
    print(f"promptfoo 설정: {out} (시험 {len(config['tests'])}개, 도구 기록 등 옮기지 못한 판정 {len(skipped)}건)")
    return 0


def _iso_date(text):
    import datetime as dt
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("YYYY-MM-DD 형식") from None


def build_parser():
    ap = argparse.ArgumentParser(prog="evalkit", description="LLM 앱 출시 전 점검 키트")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="시험 문제 스키마 검사")
    v.add_argument("paths", nargs="*", default=["cases"])
    v.set_defaults(fn=cmd_validate)

    ls = sub.add_parser("list", help="유형별 개수")
    ls.add_argument("paths", nargs="*", default=["cases"])
    ls.add_argument("--private", default="private/attack_inputs.yaml")
    ls.set_defaults(fn=cmd_list)

    cp = sub.add_parser("check-private", help="비공개 입력 파일 상태(문구는 출력하지 않음)")
    cp.add_argument("--private", default="private/attack_inputs.yaml")
    cp.set_defaults(fn=cmd_check_private)

    r = sub.add_parser("run", help="시험 실행 + 보고서")
    r.add_argument("--cases", nargs="*")
    r.add_argument("--target", default="targets/shop-bot-py.yaml")
    r.add_argument("--suite", choices=["quick", "full"])
    r.add_argument("--only", help="쉼표로 구분한 시험 문제 id")
    r.add_argument("--repeats", type=int, help="모든 시험 문제의 반복 횟수를 이 값으로")
    r.add_argument("--judge-mode", choices=["off", "heuristic", "openai"], default="off")
    r.add_argument("--thresholds", default="thresholds.yaml")
    r.add_argument("--accepted-risks", default="accepted_risks.yaml")
    r.add_argument("--private", default="private/attack_inputs.yaml")
    r.add_argument("--out", default="results")
    r.add_argument("--compare", help="비교할 지난 results.json")
    r.add_argument("--gate", action="store_true", help="빨강이면 종료 코드 1")
    r.add_argument("--fail-on-yellow", action="store_true")
    r.add_argument("--today", type=_iso_date, help="수용한 위험 기한을 이 날짜(YYYY-MM-DD) 기준으로 본다(시연용, 13장)")
    r.add_argument("--allow-remote-target", action="store_true",
                   help="허락받은 시험 서버만(대상 설정에 authorized_by 필수)")
    r.set_defaults(fn=cmd_run)

    rp = sub.add_parser("report", help="results.json으로 보고서 다시 만들기")
    rp.add_argument("results")
    rp.add_argument("--compare")
    rp.add_argument("--print", action="store_true")
    rp.set_defaults(fn=cmd_report)

    ag = sub.add_parser("agreement", help="사람 라벨 vs 채점관 일치율")
    ag.add_argument("labels")
    ag.add_argument("--judge-mode", choices=["heuristic", "openai"], default="heuristic")
    ag.set_defaults(fn=cmd_agreement)

    pf = sub.add_parser("to-promptfoo", help="promptfoo 설정으로 옮기기")
    pf.add_argument("--cases", nargs="*")
    pf.add_argument("--only")
    pf.add_argument("--target", default="targets/shop-bot-py.yaml")
    pf.add_argument("--out", default="promptfoo/promptfooconfig.generated.yaml")
    pf.set_defaults(fn=cmd_to_promptfoo)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
