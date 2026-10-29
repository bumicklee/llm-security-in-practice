#!/usr/bin/env bash
# 키트 자체 점검: 문법 검사 + 단위 테스트 + 스키마 검사 + 공격 ID 등록부 검사 (모델·외부 패키지·앱 없이)
# 대응: 8장(판정기도 시험한다), 12장(CI 전에 로컬에서)
# 실행: bash eval-kit/scripts/check.sh   (어디서든)
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
LAB="$(cd "$KIT/.." && pwd)"
# 다른 스택(13-6) 끝에서 끝까지 테스트가 띄우는 상담봇. tests/test_e2e_stub.py와 같은 순서로 찾고, 없으면 그 4개는 건너뛴다
BOT=""
for d in "${SUPPORT_BOT_DIR:-}" "$LAB/extras/support-bot-python" "$LAB/../extras/support-bot-python"; do
  if [ -n "$d" ] && [ -f "$d/app.py" ]; then BOT="$(cd "$d" && pwd)"; break; fi
done
echo "[1/5] 문법 검사"
python3 -m py_compile "$KIT"/evalkit/*.py "$KIT"/tests/*.py
if [ -n "$BOT" ]; then python3 -m py_compile "$BOT"/*.py; else echo "  support-bot-python 없음 → 상담봇 문법 검사·끝에서 끝까지 테스트 4개 건너뜀"; fi
echo "[2/5] 키트 단위 테스트"
(cd "$KIT" && python3 -m unittest discover -s tests 2>&1 | tail -1)
echo "[3/5] 시험 문제 스키마(shop-bot 50개)"
(cd "$KIT" && python3 -m evalkit validate cases)
echo "[4/5] 시험 문제 스키마(portable 5개 · 22장 capstone 6개)"
(cd "$KIT" && python3 -m evalkit validate cases/portable && python3 -m evalkit validate cases/capstone)
echo "[5/5] 공격 자리표시 ID 등록부"
(cd "$LAB" && python3 -I scripts/check-attack-ids.py .)
