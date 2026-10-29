# 프롬프트: MCP 서버 연결 전 점검

- **쓰는 곳:** 10장 10.3~10.4, 수업 5-6
- **도구:** Claude Code
- **목적:** 남이 만든 MCP 서버를 붙이기 전에 넘어오는 도구 목록·권한·출처를 점검표(표 10-1)로 평가하고, 허용 목록 게이트 초안을 만든다.

## 프롬프트 본문

```text
랩의 가짜 MCP 서버({mcp_주소})를 붙이기 전에 점검해라. 도구는 실행하지 마라(tools/call 금지).

1. python -I attack-kit/mcp_tool_review.py {mcp_주소} 를 실행하고 결과를 보여 줘(venv를 켠 상태, mcp SDK {mcp_버전} 필요).
2. tools/list 결과의 각 도구에 대해: 이름 | 하는 일 | 읽기/쓰기/외부 전송 | 설명 안에 지시처럼 보이는 표지가 있나 | 붙인다/뺀다/조건부
3. 점검표 7항목에 답: 인증 방식 | 받을 도구 목록(허용 목록) | 권한 범위 | 호출 로그 | 출처(누가 만들고 관리하나) | 버전 고정(사양 판 포함) | 끄는 방법
4. Python 앱에 붙인다면: mcp SDK의 Client 로 도구 목록을 받고, 허용 목록에 든 이름만 남기는 게이트 함수와,
   붙일 도구를 앱의 도구 허용 목록(등급 포함)에 먼저 등록해야 시작되게 하는 검사 초안.
   langchain-mcp-adapters 를 쓰려면 그 패키지가 요구하는 mcp 버전 범위를 먼저 확인한다. API 이름이 불확실하면 # 확인 필요.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{mcp_주소}` | `http://127.0.0.1:8095/mcp` (가짜 서버: `python -I tools/fake_mcp.py &`) |
| `{mcp_버전}` | 2.3.0 (부록 C) |

## 기대 출력 예

랩 실측 `samples/lab-app-py/_실측/5-6_mcp-review.txt`:

```text
서버: {'name': 'fake-mcp', 'version': '0.1.0'}  도구 5개
  [LOW   ] search_products    읽기 전용 표시(서버 주장)
  [HIGH  ] export_customers   대량 내보내기      → 뺀다
  [HIGH  ] send_email         외부 전송          → 뺀다
  [HIGH  ] run_shell          명령 실행          → 뺀다
  [MEDIUM] get_coupon_rules   설명 속 지시 표지(도구 설명도 모델 입력이다) → 뺀다
```

게이트 랩 정답: `shopbot/mcp/client.py`(`list_server_tools`, `mcp.Client`), `shopbot/mcp/gate.py`(`McpToolGate`, 설정 `mcp_allowed_tools`), `shopbot/tools/registry_check.py`(`verify_tool_allowlist`). mcp 프로필 실측: `_실측/5-6_mcp-client.txt`.

## 주의

- `readOnlyHint` 같은 표시는 서버의 "주장"이다. 믿지 말고 코드·문서로 확인한다.
- 점검기는 127.0.0.1 밖 주소를 거부한다(`require_loopback`). 회사 MCP 서버를 점검할 때는 담당자 허락을 받고, 점검기를 복사해 주소 검사를 그 팀 기준으로 바꾼다.
- langchain-mcp-adapters 0.3.2는 `mcp<2.0.0`을 요구해 mcp 2.3.0과 함께 설치할 수 없다(10장, 부록 C). 새 판이 나오면 다시 확인한다.
