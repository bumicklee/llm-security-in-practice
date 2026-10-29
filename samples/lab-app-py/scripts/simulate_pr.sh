#!/usr/bin/env bash
# PR 하나를 로컬에서 흉내 낸다: 파일을 잠깐 바꾸고 → .github/workflows/llm-gate.yml의 세 잡 명령을 차례로 → 되돌린다(19장, 수업 12-4).
#   잡 pytest    : 워크플로와 같은 세 단계(공격·단위·앱 → capstone → contract). 한 단계가 빨개지면 그 잡의 뒤 단계는 건너뛴다(Actions와 같다)
#   잡 eval-gate : 키트 점검 → 가짜 LLM(127.0.0.1:8070)·uvicorn(LAB_PROFILES=eval, 127.0.0.1:8080) → quick 묶음 --gate
#                  워크플로에 needs가 없으므로 pytest 결과와 상관없이 돈다
#   잡 llm-gate  : 두 결과를 모은다(둘 다 success일 때만 GREEN)
# 실행(lab-app-py 폴더, .venv 켠 상태): bash scripts/simulate_pr.sh <none|prompt|code>
#   none   : 아무것도 바꾸지 않은 PR(기준)
#   prompt : 빨간불 ① 프롬프트·설정을 고친 PR — shopbot/profiles/default.yaml의 secret_free_prompt·output_schema를 false로
#   code   : 빨간불 ② 방어 코드를 지운 PR — labcore/tools의 cancel_order 소유권 확인 줄을 repo.find로
# 바꾼 파일은 .lab-run/에 원본을 두고, 끝나면(오류·Ctrl+C 포함) 되돌린다. 기준선 비교(--compare)·산출물 올리기는 GitHub에서만 한다.
# 모든 값은 가짜, 127.0.0.1만. 8070·8080·8081·8082 포트가 비어 있어야 한다.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"
export PYTHONDONTWRITEBYTECODE=1
KIND="${1:-}"
RUN=.lab-run
mkdir -p "$RUN"
YML=shopbot/profiles/default.yaml
TOOL=labcore/tools/__init__.py
LLM_PID=""; APP_PID=""; RESTORE=""

restore() {
  for pid in $APP_PID $LLM_PID; do kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; done
  APP_PID=""; LLM_PID=""
  if [ -n "$RESTORE" ]; then cp "$RUN/pr-sim.orig" "$RESTORE" && echo "되돌림: $RESTORE"; RESTORE=""; fi
}
trap restore EXIT

case "$KIND" in
  none) echo "PR: 바꾼 파일 없음(기준)" ;;
  prompt)
    cp "$YML" "$RUN/pr-sim.orig"; RESTORE="$YML"
    sed -i.bak 's/  secret_free_prompt: true/  secret_free_prompt: false/; s/  output_schema: true/  output_schema: false/' "$YML" && rm -f "$YML.bak"
    echo "PR ①(프롬프트·설정): $YML"; diff "$RUN/pr-sim.orig" "$YML" | grep -E '^[<>]' ;;
  code)
    cp "$TOOL" "$RUN/pr-sim.orig"; RESTORE="$TOOL"
    python - "$TOOL" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
old = '        o = self._owned(user, order_id)\n        if o is None:\n            self.audit.denied(user.user_id, "cancelOrder"'
new = '        o = self.repo.find(order_id)   # 소유권 확인을 지운 PR\n        if o is None:\n            self.audit.denied(user.user_id, "cancelOrder"'
assert old in s, "바꿀 줄을 찾지 못함"
open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
PY
    echo "PR ②(방어 코드): $TOOL"; diff "$RUN/pr-sim.orig" "$TOOL" | grep -E '^[<>]' ;;
  *) echo "쓰는 법: bash scripts/simulate_pr.sh <none|prompt|code>"; exit 2 ;;
esac

step() {   # step <이름> <명령> : 명령을 보이고 돌린 뒤 종료 코드를 돌려준다
  echo "  - $1"; echo "    \$ $2"
  bash -c "$2" 2>&1 | sed 's/^/    /'
  return "${PIPESTATUS[0]}"
}

echo
echo "[잡 pytest]"
PYTEST=success
step "방어 코드·앱 공격 테스트" "set -o pipefail; python -m pytest tests/attack tests/unit tests/app -q --tb=no 2>&1 | grep -E 'FAILED|passed|failed'" || PYTEST=failure
if [ "$PYTEST" = success ]; then
  step "22장 종합 실습(capstone)" "set -o pipefail; python -m pytest -m capstone -q --tb=no 2>&1 | tail -1" || PYTEST=failure
fi
if [ "$PYTEST" = success ]; then
  step "계약·가짜 LLM 대조(contract)" "set -o pipefail; python -m pytest -m contract -q --tb=no 2>&1 | tail -1" || PYTEST=failure
fi
echo "  → pytest: $PYTEST"

echo
echo "[잡 eval-gate] (needs 없음 → pytest 결과와 상관없이 돈다)"
EVAL=success
step "키트 점검" "set -o pipefail; (cd eval-kit && python -m unittest discover -s tests 2>&1 | tail -1) && (cd eval-kit && python -m evalkit validate cases | tail -1) && python -I scripts/check-attack-ids.py . | tail -1" || EVAL=failure
if [ "$EVAL" = success ]; then
  python -I tools/fake_llm.py > "$RUN/pr-sim-fake-llm.log" 2>&1 & LLM_PID=$!
  LAB_PROFILES=eval python -m uvicorn shopbot.main:app --host 127.0.0.1 --port 8080 > "$RUN/pr-sim-app.log" 2>&1 & APP_PID=$!
  up=""
  for _ in $(seq 1 120); do curl -sf http://127.0.0.1:8082/healthz > /dev/null 2>&1 && curl -sf http://127.0.0.1:8070/v1/models > /dev/null 2>&1 && { up=1; break; }; sleep 0.25; done
  if [ -z "$up" ]; then echo "    shop-bot-py가 뜨지 않았습니다"; tail -20 "$RUN/pr-sim-app.log"; EVAL=failure; fi
fi
if [ "$EVAL" = success ]; then
  step "출시 게이트 실행(PR = quick)" "cd eval-kit && python -m evalkit run --target targets/shop-bot-py.yaml --suite quick --gate --out results" || EVAL=failure
fi
echo "  → eval-gate: $EVAL"

echo
echo "[잡 llm-gate] pytest=$PYTEST eval-gate=$EVAL"
if [ "$PYTEST" = success ] && [ "$EVAL" = success ]; then echo "llm-gate: GREEN — 두 층 모두 통과"; CODE=0
else echo "llm-gate: RED — 머지 불가(빨간 층의 로그를 본다)"; CODE=1; fi
restore
exit $CODE
