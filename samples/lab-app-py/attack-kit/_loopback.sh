#!/usr/bin/env bash
# 목적: attack-kit 공용 안전장치. 대상 주소의 호스트가 정확히 127.0.0.1 이 아니면 즉시 종료한다.
#       localhost 는 hosts 파일에 따라 다른 곳을 가리킬 수 있어 받지 않는다.
#       "http://127.0.0.1:8080@다른호스트/" 처럼 사용자 정보(@)로 호스트를 바꾸는 모양도 거부한다.
# 사용: source "$(dirname "$0")/_loopback.sh"; require_loopback "$TARGET"
require_loopback() {
  local url="$1"
  case "$url" in
    *@*|*\\*) echo "거부: 주소에 @ 나 \\ 가 있으면 받지 않습니다. 받은 값: $url" >&2; exit 2 ;;
  esac
  if printf '%s' "$url" | grep -qE '^http://127\.0\.0\.1(:[0-9]{1,5})?(/[^[:space:]]*)?$'; then
    return 0
  fi
  echo "거부: 대상은 http://127.0.0.1(내 PC의 랩)만 허용합니다. 받은 값: $url" >&2
  exit 2
}
