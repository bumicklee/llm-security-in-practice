"""MCP 도구 허용 목록 게이트. 받은 도구 중 mcp_allowed_tools(기본 search_products)만 남긴다(표 10-1 2번).

시작할 때 "서버가 준 도구"와 "게이트를 지난 도구"를 로그로 찍는다. 이 랩은 MCP 도구를 채팅에 붙이지 않는다.
붙이려면 9장처럼 ToolAllowlist에 이름과 등급을 먼저 적는다(registry_check가 시작을 막는다).
"""
import logging

from shopbot.mcp.client import list_server_tools

log = logging.getLogger("shopbot.mcp")


class McpToolGate:
    def __init__(self, allowed):
        self.allowed = set(allowed)

    def filter(self, tools: list[dict]) -> list[dict]:
        return [t for t in tools if t["name"] in self.allowed]


async def report_mcp_tools(url: str, allowed) -> dict:
    got = await list_server_tools(url)
    names = [t["name"] for t in got["tools"]]
    passed = [t["name"] for t in McpToolGate(allowed).filter(got["tools"])]
    log.warning("[mcp] 서버 %s %s · 사양 %s · 서버가 준 도구 %d개: %s", got["server"]["name"], got["server"]["version"],
                got["protocol_version"], len(names), names)
    log.warning("[mcp] 게이트(mcp_allowed_tools)를 지난 도구 %d개: %s · 채팅에는 붙이지 않음(ToolAllowlist에 없음)",
                len(passed), passed)
    return {**got, "passed": passed}
