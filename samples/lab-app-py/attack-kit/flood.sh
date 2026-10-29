#!/usr/bin/env bash
# 목적: 요금 폭탄 재현(7장 7.1, 8장 8.6). 같은 사용자로 짧은 시간에 요청을 많이 보낸다.
#       수정 전: 전부 200, 요금 대시보드(127.0.0.1:8090) 그래프 급등 / 수정 후: 10번 뒤 429, 그래프 평평.
# 실행: ./attack-kit/flood.sh [요청수=50] [대상=http://127.0.0.1:8080]
# 안전: 대상이 127.0.0.1이 아니면 실행을 거부한다.
set -euo pipefail
source "$(dirname "$0")/_loopback.sh"
COUNT="${1:-50}"
TARGET="${2:-http://127.0.0.1:8080}"
require_loopback "$TARGET"
USER_PASS="bob:FAKE-pass-0000"   # 가짜 계정

ok=0; limited=0; other=0   # macOS 기본 bash 3.2에서도 돌도록 연관 배열을 쓰지 않는다
for i in $(seq 1 "$COUNT"); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -u "$USER_PASS" -H 'Content-Type: application/json' \
    -d "{\"message\":\"배송 문의 ${i}\"}" "$TARGET/api/chat" || true)
  case "$code" in
    200) ok=$((ok + 1)) ;;
    429) limited=$((limited + 1)) ;;
    *) other=$((other + 1)) ;;
  esac
done
echo "요청 ${COUNT}번 결과: 200=$ok  429=$limited  기타=$other"
echo "요금 대시보드: http://127.0.0.1:8090"
