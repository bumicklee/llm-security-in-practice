#!/usr/bin/env bash
# 가짜 LLM과 shop-bot-py(uvicorn)를 잠깐 띄우고 → 시험을 돌리고 → 띄운 것만 내린다. 수업 시연(8-2, 12장)과 스킬에서 쓴다.
# 대응: 설계 2.8, 8-2(첫 시험), 12장(게이트).
# 실행 예(lab-app-py 폴더 또는 어디서든):
#   bash eval-kit/scripts/serve_and_run.sh                         # 수정 후(eval), quick 묶음 → GREEN 기대
#   bash eval-kit/scripts/serve_and_run.sh full before,eval        # 위치 인자: 묶음 프로필 → 수정 전 RED 기대
#   PROFILE=before,eval EXTRA="--cases cases/starter --repeats 1" bash eval-kit/scripts/serve_and_run.sh
# 필요: lab-app-py/.venv(pip install -r requirements.lock). PY로 다른 파이썬을 줄 수 있다.
# 이미 127.0.0.1:8082/healthz에 앱이 떠 있으면 그 앱을 그대로 쓴다(프로필은 확인할 수 없으니 주의 문구만 낸다).
set -uo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
LAB="$(cd "$KIT/.." && pwd)"
SUITE="${1:-${SUITE:-quick}}"
PROFILE="${2:-${PROFILE:-eval}}"
JUDGE="${JUDGE:-off}"
EXTRA="${EXTRA:-}"
PY="${PY:-$LAB/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
LLM_PID=""
BOT_PID=""

case ",$PROFILE," in
  *,eval,*) ;;
  *) echo "PROFILE에 eval이 없습니다($PROFILE). 평가 키트는 eval 프로필(reset·fixtures·trace)이 필요합니다."; exit 2 ;;
esac

cleanup() {
  for pid in $BOT_PID $LLM_PID; do
    kill "$pid" > /dev/null 2>&1 || true
    wait "$pid" 2> /dev/null || true   # 포트가 풀릴 때까지 기다린다(바로 다음 실행이 옛 앱을 쓰지 않게)
  done
}
trap cleanup EXIT

if ! curl -sf http://127.0.0.1:8070/v1/models > /dev/null 2>&1; then
  (cd "$LAB" && exec "$PY" -I tools/fake_llm.py) > "$KIT/.fake-llm.log" 2>&1 &
  LLM_PID=$!
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8070/v1/models > /dev/null 2>&1 && break; sleep 0.5; done
fi

if curl -sf http://127.0.0.1:8082/healthz > /dev/null 2>&1; then
  echo "이미 떠 있는 shop-bot-py를 씁니다(프로필 확인 불가 — PROFILE=$PROFILE 로 띄운 앱인지 직접 확인하세요)."
else
  (cd "$LAB" && LAB_PROFILES="$PROFILE" exec "$PY" -m uvicorn shopbot.main:app --host 127.0.0.1 --port 8080) > "$KIT/.shop-bot.log" 2>&1 &
  BOT_PID=$!
  # 첫 요청 때 앱을 만든다(_LazyApp) → lifespan이 관리 앱(8082)을 띄울 때까지 기다린다
  for _ in $(seq 1 60); do curl -sf http://127.0.0.1:8082/healthz > /dev/null 2>&1 && break; sleep 0.5; done
fi

cd "$KIT"
if [ -n "$EXTRA" ]; then
  # shellcheck disable=SC2086
  "$PY" -m evalkit run --target targets/shop-bot-py.yaml --judge-mode "$JUDGE" --gate $EXTRA
else
  "$PY" -m evalkit run --target targets/shop-bot-py.yaml --suite "$SUITE" --judge-mode "$JUDGE" --gate
fi
CODE=$?
echo "종료 코드: $CODE (0=초록·노랑, 1=빨강, 2=설정 오류, 3=연결 실패) · 프로필 $PROFILE"
exit $CODE
