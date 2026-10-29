#!/usr/bin/env bash
# 목적: 훅 두 개가 fail closed인지 스스로 확인한다(설계 5.8, 2장 2.5·수업 1-8 안전 수칙). 깨진 입력·모양이 다른 입력·정상 입력을 넣어
#       종료 코드를 본다(2 = 차단, 0 = 통과). 키 모양 값은 즉석에서 만들고 파일에 남기지 않는다.
# 실행: 저장소 루트(llm-security-in-practice)에서 bash skills/hooks/test-hooks.sh · 내 프로젝트에 설치한 뒤에는 bash .claude/hooks/test-hooks.sh
#       (이 스크립트는 자기 폴더의 한 칸 위로 가서 hooks/<훅>.sh 를 부르므로 skills/ 와 .claude/ 어디서나 같다)
# 기록: samples/lab-app-py/_실측/1-8_hooks-fail-closed.txt (scripts/capture_all.sh 의 1-8_hooks-fail-closed 항목, 2차 검증 B F-05)
# 등록 방식(settings.example.json): exec 형식("command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/<훅>.sh", "args": [])
#       + "onFailure": "block"(Claude Code v2.1.295 이상). exec 형식은 스크립트를 직접 실행하므로 실행 권한(chmod +x)이 필요하다.
set -u
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
t() { local hook="$1" desc="$2" input="$3"; printf '%s' "$input" | bash "hooks/$hook" 2>"$TMP/err"; rc=$?; printf '%-28s %-44s exit=%s %s\n' "$hook" "$desc" "$rc" "$(tr '\n' ' ' < "$TMP/err")"; }
L=block-non-loopback.sh; S=block-real-secrets.sh
t $L "깨진 JSON" '{"tool_name":"Bash","tool_input":'
t $L "빈 입력" ''
t $L "JSON 배열(모양 다름)" '[1,2]'
t $L "tool_input이 문자열" '{"tool_name":"Bash","tool_input":"x"}'
t $L "command가 숫자" '{"tool_name":"Bash","tool_input":{"command":5}}'
t $L "밖 주소(flood.sh)" '{"tool_name":"Bash","tool_input":{"command":"./attack-kit/flood.sh 50 http://203.0.113.5:8080"}}'
t $L "@로 호스트 바꾸기" '{"tool_name":"Bash","tool_input":{"command":"curl http://127.0.0.1:8080@203.0.113.5/api/chat"}}'
t $L "localhost" '{"tool_name":"Bash","tool_input":{"command":"curl http://localhost:8080/api/chat"}}'
t $L "evalkit 밖 대상" '{"tool_name":"Bash","tool_input":{"command":"python3 -m evalkit run --target t.yaml http://203.0.113.5"}}'
t $L "127.0.0.1(통과)" '{"tool_name":"Bash","tool_input":{"command":"./attack-kit/flood.sh 50 http://127.0.0.1:8080"}}'
t $L "관련 없는 명령(통과)" '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'
K="sk-$(printf 'x%.0s' $(seq 24))"
t $S "깨진 JSON" '{"tool_name":"Write","tool_input":{"content":'
t $S "빈 입력" ''
t $S "tool_input이 목록" '{"tool_name":"Write","tool_input":[1]}'
t $S "FAKE 없는 키 모양" "{\"tool_name\":\"Write\",\"tool_input\":{\"content\":\"api-key: $K\"}}"
t $S "FAKE 키(통과)" '{"tool_name":"Edit","tool_input":{"new_string":"api-key: sk-test-FAKE-0000aaaaaaaaaaaaaaaaaaa"}}'
t $S "평범한 글(통과)" '{"tool_name":"Write","tool_input":{"content":"hello"}}'
# python3가 PATH에 없을 때(PATH에 cat만 둔다)
mkdir -p "$TMP/nopy" && ln -s /bin/cat "$TMP/nopy/cat"
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | env PATH="$TMP/nopy" /bin/bash hooks/$L 2>"$TMP/err"; printf '%-28s %-44s exit=%s %s\n' "$L" "python3 없음(PATH에 cat만)" "$?" "$(tr '\n' ' ' < "$TMP/err")"
# exec 형식 등록에 필요한 실행 권한
for h in hooks/block-non-loopback.sh hooks/block-real-secrets.sh; do
  if [ -x "$h" ]; then printf '%-28s %-44s %s\n' "$(basename "$h")" "실행 권한(exec 형식)" "ok"; else printf '%-28s %-44s %s\n' "$(basename "$h")" "실행 권한(exec 형식)" "없음 → chmod +x"; fi
done
