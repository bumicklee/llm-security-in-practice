#!/usr/bin/env bash
# 목적: Claude Code PreToolUse(Write|Edit) 훅. 파일에 "진짜처럼 보이는" 키·개인키를 쓰려 하면 막는다.
#       랩 규칙: 비밀은 FAKE가 들어간 가짜 값만(sk-test-FAKE-0000 등).
# 동작: 표준 입력 훅 JSON의 tool_input.content(Write) / tool_input.new_string(Edit)을 검사.
#       막을 때 exit 2 + 표준 오류에 이유. 통과는 exit 0.
# 실패 시(fail closed, 설계 5.8): 입력을 해석하지 못하거나 검사 중 예외가 나면 exit 2로 막는다.
#       메시지 "blocked: hook error, fail closed (<예외 이름>)". python3가 없거나 예상 밖 종료 코드여도 막는다(08 10장과 같은 꼴).
# 필요: python3 (-I 격리 모드)
set -u
INPUT="$(cat)" || { echo "blocked: hook error, fail closed (stdin)" >&2; exit 2; }
printf '%s' "$INPUT" | python3 -I -c '
import json, re, sys

PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "API 키 모양"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "개인키"),
    (r"AKIA[0-9A-Z]{16}", "클라우드 접근 키 모양"),
]

try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        raise TypeError("hook input is not an object")
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        raise TypeError("tool_input is not an object")
    text = "\n".join(str(ti.get(k, "")) for k in ("content", "new_string"))
    hit = None
    for pat, name in PATTERNS:
        for m in re.finditer(pat, text):
            if "FAKE" not in m.group(0):
                hit = name
                break
        if hit:
            break
except Exception as exc:
    sys.stderr.write("blocked: hook error, fail closed (%s)\n" % type(exc).__name__)
    sys.exit(2)
if hit:
    sys.stderr.write("차단: 파일에 %s이(가) 들어갑니다. 랩에서는 FAKE가 들어간 가짜 값만 씁니다(예: sk-test-FAKE-0000).\n" % hit)
    sys.exit(2)
sys.exit(0)
'
rc=$?
case "$rc" in
  0|2) exit "$rc" ;;
  *) echo "blocked: hook error, fail closed (exit $rc)" >&2; exit 2 ;;
esac
