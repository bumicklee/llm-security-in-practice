#!/usr/bin/env bash
# 목적: Claude Code PreToolUse(Bash) 훅. 공격 실습 명령(attack-kit, /api/chat, 가짜 LLM 호출, evalkit 등)이
#       127.0.0.1 밖을 겨냥하면 실행 전에 막는다. 랩 프로젝트 전용.
# 동작: 표준 입력으로 훅 JSON({"tool_name":"Bash","tool_input":{"command":"..."}})을 받는다.
#       막을 때 exit 2 + 표준 오류에 이유(Claude에게 전달됨). 통과는 exit 0.
#       - 스킴이 있는 주소(http://, https:// 등)는 호스트가 정확히 127.0.0.1 이어야 한다.
#       - 주소에 @ 가 있으면(사용자 정보로 호스트를 바꾸는 모양) 막는다.
#       - 스킴 없이 "호스트:포트/api/..." 처럼 쓴 것도 호스트를 본다.
#       - localhost 는 hosts 파일에 따라 다른 곳을 가리킬 수 있어 받지 않는다.
# 실패 시(fail closed, 설계 5.8): 입력을 해석하지 못하거나(깨진 JSON·모양이 다름) 검사 중 예외가 나면 exit 2로 막는다.
#       메시지 "blocked: hook error, fail closed (<예외 이름>)". python3가 없거나 예상 밖 종료 코드여도 막는다(08 10장과 같은 꼴).
# 한계: 셸 변수($TARGET)로 넘긴 주소는 여기서 펼쳐 볼 수 없다. 그래서 attack-kit 스크립트·evalkit도
#       실행할 때 127.0.0.1 밖을 한 번 더 막는다(두 겹). 훅은 보조이고 보안 경계가 아니다.
# 설치: .claude/hooks/ 에 복사, chmod +x, settings.json 의 hooks.PreToolUse 에 등록(../settings/settings.example.json)
# 필요: python3 (-I 격리 모드)
set -u
INPUT="$(cat)" || { echo "blocked: hook error, fail closed (stdin)" >&2; exit 2; }
printf '%s' "$INPUT" | python3 -I -c '
import json, re, sys


def check(cmd):
    from urllib.parse import urlsplit
    # 공격 실습과 관련된 명령만 본다
    if not re.search(r"attack-kit|flood\.sh|run-attacks|run_attacks|/api/chat|/api/products|/api/reviews|/api/lab|"
                     r"/v1/chat/completions|mcp_tool_review|/mcp\b|evalkit|serve_and_run|promptfoo|garak", cmd):
        return None
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"\x27<>]+", cmd):
        url = m.group(0)
        u = urlsplit(url)
        if "@" in u.netloc or "\\" in url or u.hostname != "127.0.0.1":
            return url
    # 스킴 없이 쓴 호스트[:포트]/경로
    for m in re.finditer(r"(?<![\w/.:@-])([A-Za-z0-9._@-]+)(?::\d+)?/(?:api|v1|mcp)\b", cmd):
        if m.group(1) != "127.0.0.1":
            return m.group(0)
    return None


try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        raise TypeError("hook input is not an object")
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        raise TypeError("tool_input is not an object")
    cmd = ti.get("command", "") or ""
    if not isinstance(cmd, str):
        raise TypeError("command is not a string")
    bad = check(cmd)
except Exception as exc:
    sys.stderr.write("blocked: hook error, fail closed (%s)\n" % type(exc).__name__)
    sys.exit(2)
if bad:
    sys.stderr.write("차단: 공격 실습 명령은 http://127.0.0.1(내 PC의 랩)만 대상으로 합니다. 발견: %s\n" % bad)
    sys.exit(2)
sys.exit(0)
'
rc=$?
case "$rc" in
  0|2) exit "$rc" ;;
  *) echo "blocked: hook error, fail closed (exit $rc)" >&2; exit 2 ;;
esac
