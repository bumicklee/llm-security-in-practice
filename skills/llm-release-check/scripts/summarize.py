"""results.json을 짧은 요약으로 줄인다(스킬이 큰 파일을 통째로 읽지 않도록).

목적: llm-release-check 스킬의 3단계(교재 20장). 표준 라이브러리만 쓴다.
실행: python3 -I .claude/skills/llm-release-check/scripts/summarize.py eval-kit/results/latest/results.json [--baseline 기준/results.json]
출력: 게이트 색, 대상, 유형별 실패 수, 막는 실패 id, 경고 id, 수용한 위험, 반복 늘리기 후보, 기준 대비 새 실패.
      공격 입력 문구는 원래 results.json에도 없다(id와 유형만).
"""
import argparse
import json
import sys
from collections import Counter
from urllib.parse import urlsplit


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--baseline")
    args = ap.parse_args()
    try:
        r = load(args.results)
        m, g, cases = r["meta"], r["gate"], r["cases"]
    except (OSError, ValueError, KeyError) as e:
        print(f"요약 실패: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"게이트: {g['color'].upper()} · 묶음 {m.get('suite')} · 프롬프트 {m.get('prompt_version') or '-'} · "
          f"모델 {m.get('model')} · 채점관 {m.get('judge')} · 시험 {len(cases)}개 · 요청 {r.get('requests')}")
    base = m.get("base_url") or ""
    host = urlsplit(base).hostname if base else None
    print(f"대상: {m.get('target')} {base}" + ("" if host in (None, "127.0.0.1") else "  ← 127.0.0.1이 아니다. 멈추고 사람에게 알린다"))
    fails = Counter(c["category"] for c in cases if c["status"] == "fail")
    print("유형별 실패:", ", ".join(f"{k} {v}" for k, v in fails.most_common()) or "없음")
    print("막는 실패:", ", ".join(g["red"]) or "없음")
    print("경고:", ", ".join(g["yellow"]) or "없음")
    print("수용한 위험:", ", ".join(g["accepted"]) or "없음")
    near = [f"{c['id']}({c['pass_rate']:.0%})" for c in cases
            if c.get("pass_rate") is not None and c.get("min_pass_rate") is not None
            and abs(c["pass_rate"] - c["min_pass_rate"]) <= 0.1 and c.get("n", 0) < 10]
    print("기준선 근처·반복 적음(반복 늘리기 후보):", ", ".join(near) or "없음")
    holds = [c["id"] for c in cases if c.get("holds")]
    if holds:
        print("보류가 있는 시험 문제:", ", ".join(holds))
    if any(c.get("judge_skipped") for c in cases):
        print("주의: 채점관 미실행(규칙 판정만)")
    if m.get("judge") == "heuristic":
        print("주의: heuristic 채점관은 데모용 — 출시 판단 근거로 쓰지 않는다")
    if r.get("budget_hit"):
        print("주의: 한도 도달 —", r["budget_hit"])
    if args.baseline:
        try:
            b = {c["id"]: c for c in load(args.baseline)["cases"]}
        except (OSError, ValueError, KeyError) as e:
            print(f"기준 읽기 실패: {type(e).__name__}", file=sys.stderr)
            return 2
        new = [c["id"] for c in cases if c["status"] == "fail" and b.get(c["id"], {}).get("status") != "fail"]
        print("기준 대비 새 실패:", ", ".join(new) or "없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
