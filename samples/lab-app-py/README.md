# 쇼핑몰 상담봇 랩 (lab-app-py)

예제·소스: https://github.com/bumicklee/llm-security-in-practice.git (이 폴더는 저장소의 `samples/lab-app-py/`)

「LLM 보안 실전」 교재 1~22장 전체에서 같은 앱 하나를 고쳐 가며 쓴다. 모든 서버는 **127.0.0.1**에서만 연다. 키·사용자·비밀은 모두 가짜 값이다.
평가 키트·공격 키트는 앱을 HTTP로만 부른다. 그래서 HTTP 계약(포트·경로·본문·HTTP Basic·`X-Request-Id`·`trace.tool_calls`·eval 관리 API)을 `tests/app/test_http_contract.py`로 고정해 둔다.

## 구성

| 폴더 | 내용 |
| --- | --- |
| `labcore/` | 순수 Python 방어 코드와 **수정 전/후 쌍**(injection·rag·cost·tools·ssrf·output·audit·llm). FastAPI·LangChain·네트워크 없이 돈다 |
| `shopbot/` | FastAPI 0.162.0 + LangChain 1.4.7 상담봇. labcore 부품을 의존성·미들웨어·`@tool`(ToolRuntime)로 연결. 프로필: 기본(수정 후)·`before`·`eval`·`lmstudio`·`external`·`redis`·`mcp`(`shopbot/profiles/`) |
| `tools/` | 가짜 LLM(`fake_llm.py`), 가짜 요금 대시보드(`bill_board.py`), 캐시 적중률(`cache_hit_rate.py`) — 표준 라이브러리만, `python -I`로 실행. 가짜 MCP(`fake_mcp.py`)만 mcp SDK 2.3.0. `_golden/`은 가짜 LLM에서 녹화해 둔 요청·응답 68쌍(규칙이 몰래 바뀌지 않았는지 보는 정답지) |
| `tests/` | pytest. `attack/`·`unit/`(labcore 49개), `app/`(FastAPI 12개 + 계약), `capstone/`(22장, `-m capstone`), `golden/`(가짜 LLM 녹화 답 대조, `-m contract`) |
| `attack-kit/` | 공격 유형 자리표시 입력, `flood.sh`, `run-attacks.sh`, `wobble.sh`, `mcp_tool_review.py`. 대상이 127.0.0.1이 아니면 실행 거부 |
| `eval-kit/` | 평가 키트(**이 폴더가 유일한 원본**). 시험 문제 50개 + capstone 6 + portable 5. 대상 `targets/shop-bot-py.yaml`(기본), 다른 스택 예 `targets/support-bot-python.yaml` |
| `docker-compose.yml` | 전체를 한 번에. 포트는 모두 `127.0.0.1:` 바인딩. 선택 `redis` 프로필은 `redis:8.10.3` |
| `.github/workflows/llm-gate.yml` | 잡 세 개: `pytest`(3.11·3.14)와 `eval-gate`(가짜 LLM + uvicorn eval 프로필 + 게이트)는 **서로 기다리지 않고** 함께 돈다 → `llm-gate`가 두 결과를 모은다(필수 상태 검사). 액션은 커밋 SHA 고정, checkout `persist-credentials: false`. 로컬 흉내: `bash scripts/simulate_pr.sh <none\|prompt\|code>` |
| `_실측/` | 이 랩에서 실제로 돌린 출력(`<수업>_<이름>.txt`). `scripts/capture_all.sh`가 다시 만든다 |

## 실행 순서(도커 없이, 수업 1-6)

명령은 한 줄씩 그대로 붙여 넣는다(맥 기본 zsh는 대화형에서 `#`을 주석으로 읽지 않아 명령 블록에 주석을 두지 않는다). Python은 3.11 이상이면 된다(예는 3.14). 가짜 LLM은 127.0.0.1:8070, 상담봇은 127.0.0.1:8080에 뜨고 관리 앱 127.0.0.1:8082/healthz도 같이 뜬다. 서버는 venv를 켠 상태에서 `python -m uvicorn`으로 띄운다. venv를 켠 뒤 pyenv 오류(`version '3.14' is not installed`)가 나면 `rehash`를 치고, 그래도 나면 `pyenv install 3.14` 또는 Homebrew python3.14로 venv를 만든 뒤 `.venv/bin/python -m uvicorn …`으로 띄운다.

```bash
git clone https://github.com/bumicklee/llm-security-in-practice.git && cd llm-security-in-practice/samples/lab-app-py
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.lock
source .venv/bin/activate
python -I tools/fake_llm.py &
python -m uvicorn shopbot.main:app --host 127.0.0.1 --port 8080
```

- 수정 전: `LAB_PROFILES=before python -m uvicorn …` · 평가 키트 연결: `LAB_PROFILES=eval` 또는 `before,eval`
- 방어 하나만 바꾸기: `LAB_DEFENSE_OFF=input_guard` / `LAB_DEFENSE_ON=secret_free_prompt`(스위치 11개 이름은 `shopbot/settings.py`)
- 한 번에: `docker compose up --build`(평가 키트는 호스트에서 띄운 uvicorn에 붙인다. 컨테이너 안 eval 프로필은 403)

## 수정 전/후 쌍 (빨강 → 초록)

차례대로: 수정 후 49개 초록 → 수정 전 공격 테스트 23개 빨강 → 1~21장 전체(labcore 49 + 앱 12 = 61) → 22장 9개 초록 → 22장 수정 전 3개 빨강 → HTTP 계약(고정한 응답 본문) + 가짜 LLM 녹화 답 대조 → 평가 게이트 RED 43/50 → 평가 게이트 GREEN.

```bash
pytest tests/attack tests/unit
pytest tests/attack tests/unit --lab-target=before
pytest
pytest -m capstone
pytest -m capstone --lab-target=before
pytest -m contract
bash eval-kit/scripts/serve_and_run.sh full before,eval
bash eval-kit/scripts/serve_and_run.sh full eval
```

| 장 | 수정 전 | 수정 후 | 지키는 테스트 |
| --- | --- | --- | --- |
| 3~4 | `NaiveSupportBot`, `SystemPrompts.BEFORE` | `GuardedSupportBot`(InputGuard·PiiMasker·ReplyPolicy) | `tests/attack/test_prompt_injection.py` |
| 5 | `NaiveRagAnswerer` | `GuardedRagAnswerer`(IngestionScanner·DocumentFencer·GroundingPolicy) | `test_indirect_injection.py` |
| 6 | `UnfilteredRetriever` | `TenantScopedRetriever` | `test_tenant_isolation.py` |
| 7~8 | `OpenGateway`, `SharedKeyCache` | `LimitedGateway`, `ScopedCache` | `test_rate_limit.py`·`test_token_budget.py`·`test_cache_isolation.py` |
| 9 | `TrustingOrderTools` | `AuthorizedOrderTools` + `ApprovalQueue`·`ApprovalService` | `test_tool_authorization.py` |
| 10 | `NaiveUrlFetcher` | `GuardedUrlFetcher` + `UrlFetchGuard` | `test_ssrf.py` |
| 11 | `ReplyRenderer.RAW`, `PromptLogPolicy.raw` | `ReplyRenderer.ESCAPED`, `PromptLogPolicy.safe`, `AuditLog` | `test_output_and_log.py` |
| 22 | `TrustingCouponTools` | `AuthorizedCouponTools` + `CouponLedger` + `approver_of`(요청자 ≠ 승인자, 같은 테넌트 직원) | `tests/capstone/` |

## 저장소로 올릴 때(이 폴더 = 저장소 루트)

- 평가 키트 단위 테스트(`eval-kit/tests`)는 다른 스택 예제 `support-bot-python`을 `SUPPORT_BOT_DIR` → `extras/support-bot-python`(이 폴더 안) → `../extras/support-bot-python`(저장소 루트의 `samples/extras/`) 순서로 찾는다. 없으면 상담봇을 띄우는 4개만 **건너뛴다**(실패 아님, `OK (skipped=4)`).
- 공격 ID 검사 `python -I scripts/check-attack-ids.py`는 인자가 없으면 **이 폴더만** 본다. 저장소 루트 전체(`prompts/`·`skills/`·`samples/extras/`까지)는 `--course`. 다른 경로도 줄 수 있고, 없는 경로는 `경로 없음` + 종료 코드 2다.

## Python·pytest 버전 메모(2026-10-28)

고정값은 그대로 둔다(`requirements.in`·`requirements.lock`). 녹화 1주 전 잠금 파일을 다시 만들 때 아래를 다시 본다.

| 항목 | 지금 | 새 판 | 메모 |
| --- | --- | --- | --- |
| Python | 3.14(`.python-version`, Docker `python:3.14.10-slim-trixie`), 최소 3.11 | **3.15**(2026-10-09, 지금 3.15.2) | 3.15는 쓰지 않는다. 잠금 파일의 `pyyaml 6.0.3`·`zstandard 0.25.0`(langgraph·langsmith가 끌어옴)에 **cp315 wheel이 없다**(PyPI 2026-10-28 확인) → `pip install --require-hashes -r requirements.lock`이 소스 빌드로 넘어가 C 컴파일러가 없으면 실패한다. 나머지 컴파일 패키지는 cp315 wheel이 있다(2차 교차 검증 A12) |
| pytest | 9.1.1 | **9.2.0**(2026-10-27) | 버린 venv에서 9.2.0으로 돌려 봤다: 61 passed · 수정 전 23 failed/26 passed · capstone 9 · contract 10 — 숫자는 같다. `parametrize`의 키워드 전용 변경은 랩에 영향 없음(`ids=`로 씀). **다만 요약 줄에 `13 warnings`가 붙는다**(langsmith 0.14.14의 `asyncio.iscoroutinefunction` DeprecationWarning이 보이게 됨) → 교재·`_실측`의 요약 줄이 달라지므로 지금은 올리지 않는다. 올릴 때 `filterwarnings`를 정하고 `_실측`을 다시 만든다 |

## 로컬 모델(LM Studio)

작성자 실측(2026-10-29, LM Studio 0.4.26, 맥북 M1 Pro 32GB)으로 확인한 설정이다. 교재 2장 2.4.

1. LM Studio에서 모델을 불러온다. 작성자는 `openai/gpt-oss-20b`(12.1GB)와 `qwen3-8b-mlx`(`lmstudio-community/Qwen3-8B-MLX-4bit`)로 쟀다.
2. 서버 화면(Developer · 창 제목 Model Server) → **Server Settings**: Server Port `1234` · **Require Authentication** 켬(**Manage Tokens**에서 토큰 만들기) · **Serve on Local Network** 끔 · **Allow per-request MCPs**·**Allow calling servers from mcp.json** 끔(랩에 필요 없음).
3. 토큰은 환경 변수로만 넘긴다(파일·명령 줄에 적지 않는다). 프로필의 `sk-test-FAKE-lmstudio`보다 환경 변수가 이긴다.

```bash
read -s OPENAI_API_KEY && export OPENAI_API_KEY
LAB_PROFILES=lmstudio LLM_MODEL=openai/gpt-oss-20b python -m uvicorn shopbot.main:app --host 127.0.0.1 --port 8080
```

- **`structured_output: "tool"`(`shopbot/profiles/lmstudio.yaml`).** 기본값 `provider`는 도구 목록과 `response_format`(json_schema)을 함께 보낸다. LM Studio 0.4.26에서는 이 조합에서 두 모델 모두 정상 질문 4개를 모두 거절했다(모델이 도구 호출 흉내·속생각을 JSON 안에 씀 → 형식 검사가 막음). `tool`이면 `ToolStrategy(BotReply)`로 최종 답을 "답 제출" 도구 호출로 받고, 모델이 글로 답하면 `reply_from_text`가 정확히 답 모양일 때만 받는다. 바꾼 뒤 gpt-oss-20b는 3개 중 0개 거절이었다. 상품 질문(RAG)도 같은 프로필에서 `bind_tools([GroundedAnswer], tool_choice="required")`로 받는다(LM Studio는 `tool_choice` 객체를 400으로 거절하고, json_schema 강제에서는 gpt-oss 답이 망가졌다).
- `LLM_BASE_URL=http://127.0.0.1:1234/v1`만 주면 기본 프로필(`provider`)이라 위 거절이 그대로 난다. `LAB_PROFILES=lmstudio`를 쓴다.
- 출력 상한: `max_completion_tokens=300`·`max_tokens=300` 모두 299토큰·`finish_reason: length`로 끊겼다(`extra_body` 필요 없음).
- 평가 게이트를 돌릴 때는 `LAB_PROFILES=lmstudio,eval`(수정 전 `lmstudio,before,eval`)로 띄우고, 대상 설정 `eval-kit/targets/shop-bot-py.yaml`의 `timeout_s`를 늘린 사본을 쓴다(작성자는 300). 공개 quick 21개(자리표시 입력): 수정 전 RED 4/21 → 수정 후 GREEN 0/21(178초).
- 기록: `_실측/1-8_lmstudio-qwen3-8b.txt`·`1-8_lmstudio-gptoss-20b.txt`·`3-6_lmstudio-gptoss-tenant.txt`·`4-4_lmstudio-max-tokens.txt`·`5-1_lmstudio-gptoss-cancel.txt`·`5-5_lmstudio-gptoss-ssrf.txt`·`11-3_lmstudio-gptoss-gate.txt`(작성자가 잰 기록, `capture_all.sh`가 다시 만들지 않는다).

## 가짜 값

| 종류 | 값 |
| --- | --- |
| API 키 | `sk-test-FAKE-0000` |
| 사용자 / 비밀번호 | `alice`·`bob`(shop-a 고객), `dave`(shop-a 직원), `carol`(shop-b 직원) / `FAKE-pass-0000` |
| 비밀 | 할인 코드 `FAKE-VIP-2026`, 관리 메모 `FAKE-ADMIN-NOTE-0000`, 카나리 `CANARY-LAB7Q2X9` |
| 주문 | 1001·1002(alice), 2001(bob), 3001(carol) |
| 공격 입력 | `[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]` 같은 자리표시만(`attack-registry.yaml`) |

## 확인 상태(2026-10-28)

- 확인함: pytest(3.14.6·3.11.14), 평가 게이트(full RED 43/50 → GREEN, quick 18/21 → GREEN), 가짜 LLM 녹화 답 대조 68쌍, `docker compose --profile redis up --build`, redis 프로필, mcp 프로필(SDK Client ↔ 가짜 MCP), CI YAML 로컬 확인.
- 2차 교차 검증 뒤 고친 것(2026-10-28): SSRF IPv6 표기, 저장소 자립(키트 테스트·공격 ID 검사 범위), CI(SHA 고정·잡 독립·요약 잡), `capture_all.sh gaps`(교재 인용 출력 27개), MCP 점검기(SDK Client).
- GitHub Actions 실제 실행: 작성자 실측(2026-10-29, GitHub 표준 러너). 공개 저장소에서 PR quick 전체 55초 · main full 전체 1분 25초, 기준선 비교와 `llm-gate` 필수 상태 검사 확인([실행 기록](https://github.com/bumicklee/llm-security-in-practice/actions/runs/40807536475)).
- [실행 필요]: Windows·Linux PC.
- LM Studio(`lmstudio` 프로필): 작성자 실측(2026-10-29, LM Studio 0.4.26) — 위 「로컬 모델(LM Studio)」.
- 【작성자 실측】: 외부 API(`external`), promptfoo·garak 실제 실행, 비공개 세트를 채운 실제 모델 full 실행.
