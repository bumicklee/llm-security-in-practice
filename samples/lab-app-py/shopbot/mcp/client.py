"""MCP 클라이언트(mcp SDK 2.3.0 Client, Streamable HTTP). mcp 프로필에서만 쓴다(10장 10.3, 수업 5-6).

langchain-mcp-adapters 0.3.2는 mcp<2.0.0을 요구해서 mcp 2.3.0과 함께 설치할 수 없다 → SDK를 직접 쓴다.
그편이 "무엇이 넘어오는지 직접 본다"(10장)와도 맞다.
"""
from mcp import Client


async def list_server_tools(url: str) -> dict:
    async with Client(url) as c:
        tools = (await c.list_tools()).tools
        info = c.server_info
        return {"server": {"name": getattr(info, "name", None), "version": getattr(info, "version", None)},
                "protocol_version": c.protocol_version,
                "tools": [{"name": t.name, "description": t.description,
                           "read_only": bool(t.annotations and t.annotations.read_only_hint)} for t in tools]}
