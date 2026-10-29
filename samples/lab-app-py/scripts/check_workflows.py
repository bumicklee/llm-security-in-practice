"""워크플로 YAML을 실제 Actions 실행 전에 로컬에서 확인한다(19장). PyYAML로 읽는다.

이름·트리거·권한·잡·needs·쓰는 액션 목록을 보이고, 각 run 블록을 bash -n으로 문법 검사한다.
공급망 점검 두 가지도 한다(2차 교차 검증 A18): 모든 uses가 40자리 커밋 SHA로 고정됐는가, checkout에 persist-credentials: false가 있는가.
실행(lab-app-py 폴더, .venv 켠 상태): python scripts/check_workflows.py .github/workflows/llm-gate.yml eval-kit/ci/llm-gate-selfhosted.yml
실제 GitHub Actions 실행은 이것으로 대신할 수 없다([실행 필요]).
"""
import re
import subprocess
import sys

import yaml


def main(paths):
    ok = True
    for f in paths:
        d = yaml.safe_load(open(f, encoding="utf-8"))
        on = d.get("on") or d.get(True)   # YAML 1.1에서 on은 True로 읽힌다
        jobs = d["jobs"]
        uses = list(dict.fromkeys(s["uses"] for j in jobs.values() for s in j.get("steps", []) if "uses" in s))
        needs = " ".join(f"{k}<-{j.get('needs') or '-'}" for k, j in jobs.items())
        matrix = {k: j["strategy"]["matrix"] for k, j in jobs.items() if "strategy" in j}
        print(f"{f}: OK · name={d['name']} · on={','.join(on)} · permissions={d.get('permissions')} · jobs={','.join(jobs)} · needs={needs}"
              + (f" · matrix={matrix}" if matrix else ""))
        print("  uses: " + " ".join(uses))
        unpinned = [u for u in uses if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", u)]
        print(f"  SHA 고정: {'ok' if not unpinned else 'FAIL ' + ' '.join(unpinned)}")
        ok &= not unpinned
        for k, j in jobs.items():
            for s in j.get("steps", []):
                if str(s.get("uses", "")).startswith("actions/checkout@"):
                    pc = (s.get("with") or {}).get("persist-credentials")
                    print(f"  persist-credentials: {k} {'ok(false)' if pc is False else 'FAIL(' + repr(pc) + ')'}")
                    ok &= pc is False
        for k, j in jobs.items():
            for i, s in enumerate(j.get("steps", [])):
                if not ("run" in s or "uses" in s):
                    raise SystemExit(f"{k}: step {i} run/uses 없음")
                if "run" in s:
                    r = subprocess.run(["bash", "-n"], input=s["run"], text=True, capture_output=True)
                    print(f"  bash -n {'ok' if r.returncode == 0 else 'FAIL'}: {k} step {i}" + ("" if r.returncode == 0 else " " + r.stderr.strip()))
                    ok &= r.returncode == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
