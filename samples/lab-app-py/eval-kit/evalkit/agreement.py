"""채점관 검증: 사람 라벨과 채점관 판정의 일치율.

목적: 채점관도 LLM이라 틀린다. 그래서 먼저 잰다. 혼동표와 일치율, '실패를 실패로 잡은 비율'을 낸다.
대응 장: 9장(9.3 사람 라벨, 9.4 일치율, 9.6 믿는 범위)
라벨 파일(JSONL) 한 줄: {"id", "case_id", "category", "rubric", "response", "human": "pass|fail|hold"}
지표 정의는 「AI로 지키는 코드와 시스템」 13.2절과 맞춘다(확인 필요: 용어 대조).
"""
import json

LABELS = ("pass", "fail", "hold")


def load_labels(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            row = json.loads(line)
            if row.get("human") not in LABELS:
                raise ValueError(f"{path}:{n} human 값은 pass|fail|hold")
            rows.append(row)
    return rows


def measure(rows, judge):
    matrix = {h: {j: 0 for j in LABELS} for h in LABELS}
    disagreements = []
    for row in rows:
        case = {"id": row["case_id"], "title": row.get("title", row["case_id"]),
                "category": row.get("category", ""), "intent": row.get("intent", ""),
                "expected_behavior": row.get("expected_behavior", "")}
        got = judge.grade(row["rubric"], case, row["response"])["verdict"]
        if got == "skip":
            raise SystemExit("채점관이 꺼져 있습니다. --judge-mode heuristic 또는 openai로 실행하세요.")
        matrix[row["human"]][got] += 1
        if got != row["human"]:
            disagreements.append({"id": row["id"], "case_id": row["case_id"], "human": row["human"], "judge": got})
    total = len(rows)
    agree = sum(matrix[l][l] for l in LABELS)
    human_fail = sum(matrix["fail"].values())
    caught = matrix["fail"]["fail"]
    judge_fail = sum(matrix[h]["fail"] for h in LABELS)
    return {
        "total": total,
        "agreement": agree / total if total else None,
        "fail_recall": caught / human_fail if human_fail else None,      # 사람이 실패라 한 것 중 채점관도 실패
        "fail_precision": caught / judge_fail if judge_fail else None,   # 채점관이 실패라 한 것 중 진짜 실패
        "hold_rate": sum(matrix[h]["hold"] for h in LABELS) / total if total else None,
        "matrix": matrix,
        "disagreements": disagreements,
    }


def format_report(res, judge_desc):
    pct = lambda v: "-" if v is None else f"{v:.0%}"  # noqa: E731
    lines = [f"채점관 검증 — {judge_desc}, 라벨 {res['total']}개",
             "",
             "사람＼채점관 |  통과 |  실패 |  보류",
             "------------+-------+-------+------"]
    for h, ko in (("pass", "통과"), ("fail", "실패"), ("hold", "보류")):
        r = res["matrix"][h]
        lines.append(f"{ko:<10}  | {r['pass']:>5} | {r['fail']:>5} | {r['hold']:>5}")
    lines += ["",
              f"일치율: {pct(res['agreement'])}",
              f"실패를 실패로 잡은 비율(재현율): {pct(res['fail_recall'])}",
              f"채점관 '실패'의 정확도(정밀도): {pct(res['fail_precision'])}",
              f"보류 비율: {pct(res['hold_rate'])}",
              "",
              "불일치:"]
    lines += [f"  {d['id']} ({d['case_id']}): 사람 {d['human']} / 채점관 {d['judge']}" for d in res["disagreements"]] or ["  없음"]
    return "\n".join(lines)
