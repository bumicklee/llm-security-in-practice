"""도구 목록만 돌려주는 가짜 MCP 서버(10장 10.3~10.4). 도구는 실행하지 않는다.

"남이 만든 도구 서버"를 붙이기 전에 무엇이 넘어오는지 보는 연습용. 일부 도구는 일부러 위험하게 설계했다.
이 파일만 mcp SDK(2.3.0, MCPServer)를 쓴다(프로토콜 정합성). 전송: Streamable HTTP, 끝점 /mcp
실행: .venv/bin/python -I tools/fake_mcp.py   → http://127.0.0.1:8095/mcp
      BIND=0.0.0.0 (컨테이너 안에서만. compose가 호스트 쪽을 127.0.0.1로 묶음)
tools/call은 항상 거부(isError)한다. 프로토콜 버전은 SDK가 정한 값을 쓴다.
랩 기본 점검은 attack-kit/mcp_tool_review.py, 앱 쪽 연결은 shopbot/mcp(mcp 프로필).
"""
import os

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

REFUSE = "가짜 서버: 실행하지 않음"
READ_ONLY = ToolAnnotations(readOnlyHint=True)

server = MCPServer(name="fake-mcp", version="0.1.0")


@server.tool(description="상품 이름으로 검색한다(읽기 전용)", annotations=READ_ONLY, structured_output=False)
def search_products(query: str) -> str:
    raise ToolError(REFUSE)


@server.tool(description="전체 고객 목록(이름·전화·주소)을 CSV로 내보낸다", structured_output=False)
def export_customers(format: str | None = None) -> str:
    raise ToolError(REFUSE)


@server.tool(description="임의 주소로 메일을 보낸다", structured_output=False)
def send_email(to: str, body: str) -> str:
    raise ToolError(REFUSE)


@server.tool(description="서버에서 셸 명령을 실행한다", structured_output=False)
def run_shell(cmd: str) -> str:
    raise ToolError(REFUSE)


@server.tool(description="쿠폰 규칙을 조회한다. [ATTACK-MCP-01: 도구 설명 속 숨은 지시 유형]", annotations=READ_ONLY,
             structured_output=False)
def get_coupon_rules() -> str:
    raise ToolError(REFUSE)


def main():
    bind = os.environ.get("BIND", "127.0.0.1")
    port = int(os.environ.get("FAKE_MCP_PORT", "8095"))
    print(f"[fake-mcp] http://{bind}:{port}/mcp (도구 목록만, 실행 안 함)", flush=True)
    # stateless + JSON 응답: attack-kit/mcp_tool_review.py 같은 단순 JSON-RPC 점검기도 세션 없이 tools/list를 받는다
    server.run("streamable-http", host=bind, port=port, streamable_http_path="/mcp", stateless_http=True, json_response=True)


if __name__ == "__main__":
    main()
