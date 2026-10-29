---
name: llm-security-review
description: FastAPI + LangChain 프로젝트의 LLM 기능을 출시 전 체크리스트 20항목(C01~C20, 입력·검색 문서·요금·도구·출력·운영)으로 읽기 전용 점검하고, 항목마다 근거 파일:줄·pytest 이름·평가 시험 ID를 표로 보고한다. LLM 보안 점검, LLM 기능 PR 리뷰, 출시 전 점검을 요청받았을 때 쓴다.
argument-hint: "[프로젝트 폴더 | PR 번호]"
allowed-tools: Read Grep Glob Bash(bash ${CLAUDE_SKILL_DIR}/scripts/scan.sh *) Bash(git diff *) Bash(gh pr diff *)
disallowed-tools: Edit Write NotebookEdit
---

# LLM 보안 점검 (출시 전 체크리스트 C01~C20, FastAPI·LangChain)

이 스킬은 **읽기 전용**이다. 파일을 고치지 않는다(이 스킬이 도는 동안 Edit·Write를 뺀다). 고칠 점은 보고서에 제안으로만 적는다. 인자: `$ARGUMENTS`.

## 언제 쓰나

- "이 FastAPI·LangChain 프로젝트 출시해도 되나 점검해 줘"
- "LLM 기능 PR 리뷰해 줘" (PR 번호나 diff가 주어지면 바뀐 부분 위주로, `../../prompts/review-llm-feature-pr.md`와 같은 기준)
- 교재 20장 20.5(체크리스트 세 칸 채우기), 21장 21.5(팀 PR 리뷰) 실습

## 절차

1. **범위 정하기.** 인자가 폴더면 그 폴더, PR 번호면 `gh pr diff <번호>`, 없으면 현재 저장소 루트. PR 리뷰면 `git diff <base>...HEAD --stat`으로 바뀐 파일부터 본다.
2. **단서 모으기.** 이 스킬 폴더의 스캐너를 돌린다(파일을 고치지 않고 네트워크도 쓰지 않는다. `.env`는 열지 않는다).
   ```bash
   bash ${CLAUDE_SKILL_DIR}/scripts/scan.sh <프로젝트 폴더>
   ```
   출력의 `[WARN]`·`[INFO]`는 **단서**일 뿐 판정이 아니다. `C00`(방어 스위치 false)은 맨 위에 따로 모은다.
3. **항목별 확인.** [checklist.md](checklist.md)의 C01~C20을 차례로, 단서가 가리키는 파일을 **직접 열어** 확인한다. FastAPI·LangChain에서 특히 볼 곳:
   - **입력 검사 의존성(C02):** 채팅·상품 Q&A 엔드포인트가 `Depends(입력 검사)`를 거치는가. 검사가 모델 호출 전에 거부하는가(예외 → 400). 요청 모델의 짧은 `max_length`가 먼저 422를 내지 않는가. 미들웨어라면 `before_agent`(요청당 한 번)인지 `before_model`(도구 루프마다)인지.
   - **시스템 프롬프트(C01)·출력 검사(C04):** 프롬프트 상수에 비밀·내부 규칙이 없는가. 나가는 답에서 비밀 모양·카나리를 보는가.
   - **출력 스키마(C03):** `create_agent(response_format=ProviderStrategy(...))` 또는 `with_structured_output(..., method="json_schema")`, 엔드포인트 `response_model`, 변환 실패 시 정해진 거절 문구.
   - **RAG(C05·C06):** 벡터 저장소에 넣는 모든 경로가 수집 검사를 지나는가. 문서를 데이터 블록으로 감싸고 근거 ID가 없으면 거절하는가.
   - **테넌트 필터(C07·C08):** `similarity_search`의 `filter`가 로그인 정보(서버 쪽 사용자)에서 만들어지는가. 필터 **문자열**에 요청 값을 이어 붙이지 않는가. 검색 진입점이 한 곳인가.
   - **로그인·레이트 리밋(C09·C10):** 모델을 부르는 모든 라우트에 인증 의존성. 레이트 리밋 키가 사용자 ID인가(slowapi에 흔히 넘기는 `get_remote_address`는 IP 기준, `key_func`는 필수 인자). 429 + `Retry-After`.
   - **토큰 한도·호출 상한(C11·C12):** `wrap_model_call` 등에서 모델 호출마다 검사, `usage_metadata` 기록, `max_tokens`, `ChatOpenAI(max_retries=…)`(openai SDK 기본 2 = 시도 3번, 앞단 재시도와 곱해짐), `trim_messages`, `ToolCallLimitMiddleware`·`ModelCallLimitMiddleware`.
   - **캐시·메트릭(C13·C14):** 캐시 키에 사용자·테넌트, 개인 답은 캐시 안 함. 메트릭 끝점이 루프백·로그인.
   - **도구 허용 목록·승인(C15·C16):** `@tool` 함수가 사용자·테넌트 ID를 모델 인자로 받지 않고 `ToolRuntime`(서버가 넣은 컨텍스트)에서 얻는가. 변경·금전 도구는 제안 → 승인 → 실행이고 돈이 나가면 요청자 ≠ 승인자인가. 시작할 때 도구 허용 목록을 검사하는가. 인자 검증(`args_schema`·도구 안 검증).
   - **SSRF·MCP(C17):** URL 도구가 허용 도메인·`getaddrinfo` 결과 전부·리다이렉트마다 재검사(`follow_redirects=False`)인가. MCP에서 받은 도구를 허용 목록 게이트로 거르는가.
   - **출력·PII 마스킹·트레이싱(C18·C19):** 모델 답을 `innerHTML` 등으로 그리지 않는가. 보내기 전(`before_model`)·저장 전 마스킹. `set_debug(True)`·트레이싱 환경 변수(`LANGSMITH_TRACING`·`LANGSMITH_TRACING_V2`·`LANGCHAIN_TRACING`·`LANGCHAIN_TRACING_V2`)가 켜진 설정이 없는가, 켜져 있으면 앱이 **시작을 거부**(fail closed)하는가.
   - **운영(C20):** 요청 ID(`contextvars`·`X-Request-Id`)로 감사 로그가 이어지는가. PR마다 pytest 잡 + 평가 게이트 잡이 도는가.
   - **부가(H01~H03):** 프로젝트에 `.claude/settings.json` 훅이 있으면 `"onFailure": "block"`(Claude Code v2.1.295 이상), exec 형식(`args`), 훅 스크립트가 깨진 입력에 `exit 2`인지(**훅 fail closed**).
4. **테스트 확인(가능하면).** 프로젝트에 테스트가 있으면 사용자의 허락을 받고 실행한다. 예: `python -m pytest -q`, 수정 전 비교는 `--lab-target=before`(랩). 실제 모델·외부 API를 부르는 테스트는 돌리지 않는다. 이 스킬은 pytest 실행 권한을 미리 주지 않는다.
5. **보고서 쓰기.** 아래 형식.

## 보고서 형식

```text
## 요약
- 통과 N / 문제 N / 확인 필요 N / 해당 없음 N
- 먼저 고칠 3개: C??, C??, C??

## 방어를 끄는 설정·변경 (있으면 맨 위, C00 포함)
| 항목 | 파일:줄 | 내용 |

## 항목별
| ID | 판정 | 근거(파일:줄) | 이유 | pytest 이름(있으면 / 없으면 제안) | 평가 시험 ID |

## 부가(Claude Code 훅)
| ID | 판정 | 근거 |
```

## 규칙

- 판정 값은 `통과`·`문제`·`확인 필요`·`해당 없음`만 쓴다. `통과`·`문제`는 근거 파일:줄이 있을 때만.
- LangChain·FastAPI API 이름은 부록 C 고정 버전(langchain 1.4.7, langchain-core 1.7.0, fastapi 0.162.0) 문서 기준. 확실하지 않으면 "확인 필요"라고 쓰고 단정하지 않는다.
- 공격 방법·우회 문장·실제 페이로드를 쓰지 않는다. 테스트 입력을 제안할 때는 `[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]`처럼 범주 + 자리 표시만.
- 키·개인정보가 보이면 보고서에 값을 옮기지 않는다(`sk-****`처럼 가린다). `.env`·비공개 입력 파일은 열지 않는다.
- 외부 서비스·운영 서버에 요청을 보내지 않는다. 실행이 필요하면 127.0.0.1의 로컬 앱만.

## 참고

- 체크리스트 원본: [checklist.md](checklist.md) (교재 20장 표 20-1, 부록 B와 같은 목록)
- 정답 예시 프로젝트: 교재 `samples/lab-app-py` (수정 전 상태: `LAB_PROFILES=before`, `pytest --lab-target=before`). 랩에 스캐너를 돌리면 남는 WARN(수정 전 프로필 `before.yaml`, 수정 전 프롬프트 `SystemPrompts.BEFORE`, 비교 경로 `ask_with_advisor`, 화면의 `outputEscape=false` 분기, 시작 거부 시연 스크립트)은 모두 **일부러 둔 재현용**이다.
- 같은 기준의 프롬프트판: `prompts/review-llm-feature-pr.md`
