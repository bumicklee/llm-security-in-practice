"""목적: MCP 서버를 붙이기 전에 도구 목록을 받아 점검표로 표시한다(10장 10.3, 표 10-1).
실행: python3 -I attack-kit/mcp_tool_review.py [http://127.0.0.1:8095/mcp]
연결: 앱(shopbot/mcp/client.py)과 같은 mcp SDK 2.3.0 `Client`(Streamable HTTP, mode="auto")로 붙는다.
      SDK는 먼저 2026-07-28 방식(요청마다 _meta에 버전, `server/discover`)으로 묻고, 서버가 모르면
      옛 initialize 핸드셰이크(~2025-11-25)로 내려간다. 점검기는 고른 사양 판을 함께 찍는다
      → 옛 판으로 내려갔다면 그 서버는 2026-07-28을 아직 모른다는 뜻이다(점검표 "버전 고정" 항목).
      (2026-10-28 이전 판은 initialize(2025-06-18)를 손으로 보냈다. 2차 교차 검증 A16에 따라 바꿨다)
판정(랩 기준, 실서비스는 팀 기준으로 바꾼다):
  HIGH  : 셸·임의 메일·대량 개인정보 내보내기처럼 되돌릴 수 없거나 밖으로 보내는 도구
  MEDIUM: readOnlyHint가 없는 도구(쓰기 가능성), 설명에 지시처럼 보이는 표지
  LOW   : 읽기 전용으로 표시된 도구(표시는 서버의 "주장"일 뿐이므로 그래도 확인)
도구를 실행하지 않는다(tools/list만).
"""
import asyncio
import sys
import urllib.parse

RISKY_WORDS = {"shell": "명령 실행", "셸": "명령 실행", "exec": "명령 실행", "email": "외부 전송", "메일": "외부 전송",
               "export": "대량 내보내기", "내보낸다": "대량 내보내기", "delete": "삭제", "삭제": "삭제", "결제": "금전"}


def require_loopback(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "http" or "@" in u.netloc or u.hostname != "127.0.0.1":
        sys.exit("거부: 랩의 가짜 MCP 서버(http://127.0.0.1)만 점검합니다")


async def fetch(url):
    from mcp import Client                      # 주소 검사를 지난 뒤에만 SDK를 불러온다
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS
    async with Client(url) as c:                # mode="auto": server/discover(2026-07-28) → 안 되면 initialize
        tools = (await c.list_tools()).tools
        return c.server_info, c.protocol_version, c.protocol_version in MODERN_PROTOCOL_VERSIONS, tools


def review(tool):
    name, desc = tool.name or "", tool.description or ""
    text = (name + " " + desc).lower()
    reasons = [v for k, v in RISKY_WORDS.items() if k in text]
    if "[attack-" in text:
        return "MEDIUM", "설명 속 지시 표지(도구 설명도 모델 입력이다)"
    if reasons:
        return "HIGH", ", ".join(sorted(set(reasons)))
    if not (tool.annotations and tool.annotations.read_only_hint):
        return "MEDIUM", "읽기 전용 표시 없음"
    return "LOW", "읽기 전용 표시(서버 주장)"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8095/mcp"
    require_loopback(url)
    info, version, modern, tools = asyncio.run(fetch(url))
    server = {"name": getattr(info, "name", None), "version": getattr(info, "version", None)}
    how = "server/discover" if modern else "옛 initialize 핸드셰이크 — 서버가 2026-07-28을 모름"
    print(f"서버: {server}  사양 {version}({how})  도구 {len(tools)}개")
    for t in tools:
        level, why = review(t)
        print(f"  [{level:<6}] {t.name:<18} {why}")
    print("\n연결 전 점검표 7항목: 교재 10장 표 10-1 (인증·도구 목록·권한 범위·로그·출처·버전 고정·비활성화 방법)")


if __name__ == "__main__":
    main()
