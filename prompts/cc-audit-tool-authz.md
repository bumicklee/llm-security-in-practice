# 프롬프트: @tool 함수 권한 감사

- **쓰는 곳:** 9장 9.2~9.5, 수업 5-2~5-4 · 22장 22.2~22.3(쿠폰 도구), 수업 14-1·14-2
- **도구:** Claude Code
- **목적:** 모델이 부를 수 있는 모든 도구를 찾아 권한 등급·소유권 확인·승인 여부를 표로 만든다.

## 프롬프트 본문

```text
이 프로젝트에서 모델이 부를 수 있는 도구를 모두 찾아라: @tool 데코레이터 함수, StructuredTool·BaseTool 하위 클래스,
create_agent(model, tools=...)·bind_tools(...) 에 넘기는 목록, MCP 등에서 동적으로 받아 붙이는 도구.
코드는 고치지 말고 표로 보고해라.

| 도구 이름 | 파일:함수 | 하는 일 | 등급(READ/CHANGE/MONEY) | "누가" 부르는지 어디서 얻나 | 소유권 확인 | 인자 검증 | 승인 단계 | 감사 로그 |

판정 규칙:
- 사용자 ID·테넌트 ID를 모델이 채우는 인자(도구 스키마에 보이는 매개변수)로 받으면 → 문제(모델이 고른 값)
- ToolRuntime(runtime.context)·InjectedToolArg·서버가 넣은 컨텍스트에서 얻으면 → 좋음
- 모델이 고른 주문 번호·금액 등은 사용자 입력처럼 형식·범위를 검사하는가(args_schema 또는 도구 안 검증)
- CHANGE/MONEY 인데 바로 상태를 바꾸면 → 문제(제안 → 승인 → 실행으로). 돈이 나가는 도구는 요청자 ≠ 승인자인가
- 허용 목록 밖 도구가 동적으로 등록될 수 있으면 → 문제(시작할 때 목록을 검사하는가)
- 도구 호출 횟수 상한(ToolCallLimitMiddleware 등)이 있는가
마지막에 고칠 순서 3개와, 각각을 증명할 pytest 테스트 이름(한국어 함수 이름 가능)을 제안.
```

## 입력 예

- 대상: `samples/lab-app-py/shopbot/tools/`, `samples/lab-app-py/labcore/tools/` (수정 전 확인은 `LAB_DEFENSE_OFF=tool_authz`일 때의 `TrustingOrderTools`·`TrustingCouponTools`)

## 기대 출력 예

```text
| cancelOrder | shopbot/tools/orders.py:cancel_order | 주문 취소 요청 | MONEY | ToolRuntime[LabContext].context.user | AuthorizedOrderTools: 있음 | ToolArgValidator.valid_order_id | ApprovalQueue.propose(PROPOSED) | AuditLog.tool_call/denied |
| issueCoupon | shopbot/tools/coupons.py:issue_coupon | 쿠폰 발급 | MONEY | ToolRuntime | AuthorizedCouponTools: 있음 | valid_amount·한도 | 같은 테넌트 직원 승인(approver_of) | 있음 |
| summarizeUrl | shopbot/tools/url_summary.py:summarize_url | URL 본문 | READ | (없음, 사용자 무관) | - | UrlFetchGuard | - | 없음 → 추가 권장 |
허용 목록: shopbot/tools/registry_check.py:verify_tool_allowlist(시작 검사) · 호출 상한: shopbot/agent/factory.py(ToolCallLimitMiddleware 전체 5·도구별 3)
```

지키는 테스트: `tests/attack/test_tool_authorization.py`(3개), `tests/unit/test_tools_unit.py`(2개), 22장 `tests/capstone/`(`pytest -m capstone`). 감사 로그 실측: `samples/lab-app-py/_실측/5-4_audit-denied.txt`.

## 주의

- LangChain `HumanInTheLoopMiddleware`는 체크포인터가 필요한 프레임워크 승인 기능이다. 써도 서버가 상태를 다시 확인하고 승인 기록을 남겨야 한다는 원칙은 같다(9장 곁글). Claude가 존재하지 않는 API를 제안하면 공식 문서로 확인한다.
- 남의 주문은 "없음"과 같은 문구로 답해 존재 여부도 흘리지 않는다.
- `ToolRuntime` 매개변수는 모델에게 보이는 도구 스키마에서 빠진다. 같은 이름의 일반 매개변수(`user_id: str`)를 따로 두면 모델이 채울 수 있다.
