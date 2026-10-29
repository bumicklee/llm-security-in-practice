"""가짜 LLM(tools/fake_llm.py)의 요청·응답 쌍을 녹화한다(설계 2.5 녹화 답 대조 시험의 정답지).

가짜 LLM 규칙을 일부러 바꿨을 때만 다시 녹화한다(그 밖에는 tests/golden이 답이 몰래 바뀌지 않았는지 지킨다).
실행(이 폴더에서):
  FAKE_LLM_PORT=18070 python -I tools/fake_llm.py &
  python -I scripts/record_fake_llm_golden.py http://127.0.0.1:18070 tools/_golden/fake_llm_cases.jsonl
안전: 대상은 http://127.0.0.1만. 입력은 tools/_golden/cases.py의 자리표시·가짜 값만."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "_golden"))
from cases import CASES  # noqa: E402


def send(base, case):
    data = None if case["body"] is None else json.dumps(case["body"], ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + case["path"], data=data, method=case["method"])
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main(base, out):
    u = urllib.parse.urlsplit(base)
    if u.scheme != "http" or u.hostname != "127.0.0.1" or "@" in u.netloc:
        sys.exit("거부: 대상은 http://127.0.0.1만")
    lines = []
    for c in CASES:
        status, body = send(base, c)
        lines.append(json.dumps({"name": c["name"], "method": c["method"], "path": c["path"], "body": c["body"],
                                 "status": status, "response": body}, ensure_ascii=False))
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"녹화 {len(lines)}쌍 → {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
