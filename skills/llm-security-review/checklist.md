# LLM 기능 출시 전 체크리스트 20항목 (C01~C20) — FastAPI·LangChain판

교재 20장 표 20-1(랩 정답), 부록 B(빈칸 인쇄용)와 **같은 목록·같은 ID**다. 아래 표는 20장 표 20-1을 그대로 옮겼다(2026-10-28). 표 20-1이 바뀌면 이 표도 함께 바꾼다.
"막는 코드 위치"는 랩(`samples/lab-app-py/`) 기준 이름이다. 내 프로젝트에서는 같은 역할의 코드를 찾는다. pytest 파일은 `tests/` 아래 경로, 평가 시험 ID는 `eval-kit/cases/`의 ID다. "—"는 그 층에서 시험하지 않는다는 뜻이다.

| ID | 구멍 | 항목 | 막는 코드 위치 | pytest 이름 | 평가 시험 ID | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| C01 | 입력 | 시스템 프롬프트에 비밀·내부 규칙 없음 | `labcore/injection`(`SystemPrompts.AFTER`, `DiscountService`), `shopbot/agent/factory.py`(`system_prompt`) | `unit/test_injection.py::test_수정_후_시스템_프롬프트에는_비밀이_없다` | `C-LEAK-01~06`, `C-START-03` | 4장 |
| C02 | 입력 | 입력 길이·문자·역할 흉내 검사가 에이전트 **밖**에서, 모델 호출 전에 | `labcore/injection`(`InputGuard`), `shopbot/web/chat.py`(의존성 `guard_input`) | `attack/test_prompt_injection.py::test_긴_입력은_앞단에서_거절`, `app/test_shopbot_security.py::test_긴_입력은_400` | `C-INJ-01~06`, `C-START-02` | 4장. 422가 아니라 400 |
| C03 | 입력 | 출력 스키마와 정해진 거절 문구 | `shopbot/agent/schemas.py`(`BotReply`), `factory.py`(`ProviderStrategy(BotReply)`), `labcore/injection`(`ReplyPolicy`) | `unit/test_injection.py::test_스키마를_벗어난_답은_정해진_문구로` | 모든 시험의 `response_schema`(대상 설정) | 4장 |
| C04 | 입력 | 나가는 답의 비밀 모양·카나리 검사 | `labcore/injection`(`LeakDetector`) | `attack/test_prompt_injection.py::test_직접_인젝션에도_비밀이_새지_않는다`, `app/test_shopbot_security.py::test_직접_인젝션에도_가짜_할인_코드와_카나리가_새지_않는다` | `C-LEAK-04`, `C-MT-01` | 카나리 `CANARY-LAB7Q2X9` |
| C05 | 검색 문서 | RAG 수집 전 검사·검토 대기열 | `labcore/rag`(`IngestionScanner`), `shopbot/rag/ingestion.py`(`ingest_review`) | `attack/test_indirect_injection.py::test_리뷰에_숨은_지시가_가짜_경쟁사_링크를_추천하게_만들지_못한다`, `app/test_eval_profile.py::test_시험용_리뷰는_수집_검사기를_지나_검토_대기가_된다` | `C-RAG-01~06` | 시험 리뷰도 정상 수집 경로로 넣는다 |
| C06 | 검색 문서 | 문서를 데이터 블록으로, 근거 ID 없으면 거절 | `labcore/rag`(`DocumentFencer`, `GroundingPolicy`), `shopbot/web/product_qa.py` | `unit/test_rag.py::test_근거가_없거나_검색되지_않은_문서를_인용하면_거절`, `attack/test_indirect_injection.py::test_정상_질문에는_근거_문서_ID가_붙는다` | `C-RAG-01~06`, `C-START-01`(`citedIds`) | 5장 |
| C07 | 검색 문서 | 필터 값은 로그인 정보에서 | `labcore/rag`(`TenantScopedRetriever`, `tenant_filter`), `shopbot/rag/tenant_retriever.py` | `attack/test_tenant_isolation.py`(3개) | `C-TENANT-01~03` | 6장, LLM08 |
| C08 | 검색 문서 | 검색 진입점 한 곳 | `shopbot/rag/tenant_retriever.py`(`TenantScopedRetriever.search`) | `app/test_shopbot_security.py::test_shop_a_사용자의_검색에는_shop_b_문서가_없다` | `C-TENANT-01~03` | 방법 B(Redis 질의 문자열)는 `redis` 프로필 |
| C09 | 요금 | 채팅 API 로그인 필수 | `shopbot/security.py`(`current_user` = `Depends(HTTPBasic)`) | `app/test_shopbot_security.py::test_로그인하지_않으면_채팅_API를_부를_수_없다` | — | 키트는 늘 로그인해서 부른다 |
| C10 | 요금 | 사용자별 레이트 리밋(429 + Retry-After) | `labcore/cost`(`UserRateLimiter`), `shopbot/web/rate_limit.py`(`rate_limited_user`) | `attack/test_rate_limit.py`(2개), `app/test_rate_limit_api.py::test_반복_호출은_429` | — | LLM10은 평가 키트 범위 밖. 키는 사용자 ID(IP 아님) |
| C11 | 요금 | 요청당·사용자·테넌트·전체 토큰 한도 | `labcore/cost`(`TokenBudget`), `shopbot/agent/middleware.py`(`TokenBudgetMiddleware`, `wrap_model_call`) | `attack/test_token_budget.py::test_아주_긴_입력은_모델에_닿지_않는다`, `unit/test_cost.py::test_토큰_한도_3단계` | — | 모델 호출마다 검사 |
| C12 | 요금 | 대화 창·최대 출력 토큰·재시도·도구 호출 제한 | `middleware.py`(`MessageWindowMiddleware`), `profiles/default.yaml`(`max_tokens: 300`, `max_retries: 1`), `factory.py`(`ToolCallLimitMiddleware`) | `attack/test_token_budget.py::test_대화가_길어져도_요청당_메시지_수는_창_크기를_넘지_않는다`, `unit/test_cost.py::test_재시도가_겹치면_곱해진다` | `C-MT-01~03`(대화 창) | 재시도 앞단 3 × SDK 2 = 6번 |
| C13 | 요금 | 캐시 키에 테넌트·사용자 | `labcore/cost`(`ScopedCache`) | `attack/test_cache_isolation.py::test_비슷한_질문이라도_남의_주문_답이_캐시에서_나오지_않는다` | — | |
| C14 | 요금 | 비용 메트릭과 경보 | `shopbot/metrics.py`(`lab_llm_tokens_total`, 127.0.0.1:8082, 로그인), `labcore/cost`(`CostAlert`) | `unit/test_cost.py::test_비용_경보는_비율마다_한_번씩` | — | 21장 지표 |
| C15 | 도구 | 도구 안에서 소유권 확인, 사용자는 `ToolRuntime`에서 | `labcore/tools`(`AuthorizedOrderTools`, `AuthorizedCouponTools`), `shopbot/tools/orders.py`·`coupons.py` | `attack/test_tool_authorization.py`(3개), `app/test_shopbot_security.py::test_모델이_alice_주문을_골라도_bob으로는_취소되지_않는다`, `capstone/test_coupon_tool.py`(2개) | `C-AUTHZ-01~04`, `C-PII-01~06`, `C-START-05`, (22장) `C-AUTHZ-05·06` | 9·22장 |
| C16 | 도구 | 금전·삭제 도구는 승인 큐(승인자 분리), 인자 검증, 허용 목록 | `labcore/tools`(`ApprovalQueue`, `ApprovalService.approver_of`, `ToolArgValidator`, `ToolAllowlist`), `shopbot/tools/registry_check.py` | `attack/test_tool_authorization.py::test_본인_주문도_승인_전에는_취소되지_않고_승인_후에만_바뀐다`, `unit/test_tools_unit.py`(2개), `capstone/test_approval_separation.py`(5개) | `C-TOOL-01~05`, `C-START-04`, `C-BEN-03`, (22장) `C-TOOL-06·07`, `C-MT-04`, `C-BEN-10` | 승인 대기(PROPOSED)는 통과로 센다 |
| C17 | 도구 | URL 도구 SSRF 차단·리다이렉트 재검사, MCP 연결 전 점검 | `labcore/ssrf`(`UrlFetchGuard`, `GuardedUrlFetcher`), `shopbot/tools/url_summary.py`(httpx2 `follow_redirects=False`), `shopbot/mcp/gate.py`(`McpToolGate`), `attack-kit/mcp_tool_review.py` | `attack/test_ssrf.py`(4개), `unit/test_ssrf_unit.py::test_검사_순서별_차단_사유` | — | 평가 키트 범위 밖 |
| C18 | 출력 | 화면 출력 이스케이프 | `shopbot/static/app.js`, `labcore/output`(`HtmlOutputEscaper`, `ReplyRenderer.ESCAPED`) | `attack/test_output_and_log.py::test_모델이_만든_HTML_태그는_화면에서_글자로만_보인다`, `unit/test_output.py::test_이스케이프와_허용_마크다운` | — | `ATTACK-OUT-01`은 "판정 없음(브라우저 확인)" |
| C19 | 출력 | 보내기 전·저장 전 마스킹, 프롬프트 원문 로그 끔, 보관 기간 | `labcore/output`(`PiiMasker`, `PromptLogPolicy`), `middleware.py`(`PiiMaskMiddleware`, `before_model`), `shopbot/main.py`(`check_prompt_logging`, 트레이싱 변수면 시작 거부) | `attack/test_output_and_log.py::test_프롬프트_로그에_가짜_키와_전화번호가_남지_않는다`, `unit/test_output.py::test_마스킹`·`test_보관_기간이_지나면_지운다` | `C-PII-04`, `C-START-05` | 11장 |
| C20 | 운영 | 요청 ID 감사 로그 + PR마다 두 층 시험 | `labcore/audit`(`AuditLog`), `shopbot/web/request_id.py`(`contextvars`), `.github/workflows/llm-gate.yml` | `attack/test_output_and_log.py::test_남의_주문_취소_시도를_요청_ID로_거꾸로_추적할_수_있다` | 게이트 자체(19장) | 보고서에 요청 ID가 남는다 |

판정 값: **통과**(근거 파일:줄 있음) / **문제**(근거 파일:줄 있음) / **확인 필요**(근거를 못 찾음 또는 런타임 확인 필요) / **해당 없음**(그 기능이 없음, 이유 한 줄).

## 스캐너 전용 ID (체크리스트 밖)

`scripts/scan.sh`는 C01~C20 말고 아래 단서도 낸다. 보고서에는 "부가"로 따로 적는다.

| ID | 무엇 | 확인 방법 |
| --- | --- | --- |
| C00 | 방어 스위치를 `false`로 둔 설정(프로필 YAML의 `defense.*`) | 수정 전 재현용 프로필(랩 `shopbot/profiles/before.yaml`)인지, 운영 프로필인지 연다. 운영 프로필이면 **문제** |
| H01 | 프로젝트 `.claude/settings.json`의 훅에 `"onFailure": "block"` | 훅이 실패(시작 실패·예상 밖 종료 코드·시간 초과)해도 동작을 막는다. **Claude Code v2.1.295 이상** 조건 |
| H02 | 훅을 exec 형식(`"args": []`)으로 등록 | 경로 자리표시(`${CLAUDE_PROJECT_DIR}`)를 쓰는 훅은 exec 형식을 권한다(hooks 문서) |
| H03 | 훅 스크립트가 스스로 fail closed(깨진 입력·예외면 `exit 2`) | `skills/hooks/test-hooks.sh`처럼 깨진 JSON·빈 입력·python3 없음으로 시험한다 |
