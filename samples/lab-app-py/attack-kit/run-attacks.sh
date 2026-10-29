#!/usr/bin/env bash
# 목적: attack-cases.json의 공격 유형을 랩 앱에 차례로 보내고 막힘/뚫림을 센다(4장 4.6, 12장 12.1).
#       결과 숫자는 이 스크립트가 낸 값만 표에 옮긴다(작성자 실측).
# 실행: ./attack-kit/run-attacks.sh [대상=http://127.0.0.1:8080] [시험 파일=attack-kit/attack-cases.json]
#       예) 4장 실습 완성본 20개: ./attack-kit/run-attacks.sh http://127.0.0.1:8080 attack-kit/examples/attack-cases-20.json
# 필요: curl, python3(JSON 읽기). 안전: 대상이 127.0.0.1이 아니면 거부.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/_loopback.sh"
TARGET="${1:-http://127.0.0.1:8080}"
require_loopback "$TARGET"
CASES="${2:-$DIR/attack-cases.json}"
exec python3 -I "$DIR/run_attacks.py" "$TARGET" "$CASES"
