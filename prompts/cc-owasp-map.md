# 프롬프트: OWASP LLM Top 10(2025판)을 내 코드 위치로 대응시키기

- **쓰는 곳:** 1장 1.5, 수업 1-4
- **도구:** Claude Code(프로젝트 루트에서 실행, 읽기만)
- **목적:** 내 FastAPI·LangChain 프로젝트에서 LLM01~LLM10 각각이 "어느 파일·함수"에 해당하는지, 방어 코드가 있는지, 무엇이 시험하는지 초안 표를 만든다. 최종 판단은 사람이 한다.

## 프롬프트 본문

```text
이 저장소는 FastAPI + LangChain(create_agent) 프로젝트다. 코드를 바꾸지 말고 읽기만 해라.

OWASP Top 10 for LLM Applications 2025판(LLM01~LLM10) 각 항목에 대해 아래 표를 채워라.
| 번호 | 항목 | 해당 코드 위치(파일:함수) | 지금 있는 방어(파일:줄) | 없음/부족한 점 | 지키는 시험(pytest 파일 또는 평가 묶음) |

찾을 곳(힌트):
- 입력: FastAPI 의존성(Depends), 미들웨어(before_agent·before_model·wrap_model_call), 시스템 프롬프트 상수
- 검색 문서: 벡터 저장소 add_documents·similarity_search, 리트리버, 문서를 프롬프트에 넣는 코드
- 요금: 레이트 리밋, 토큰 사용량(usage_metadata), max_tokens·max_retries, 도구·모델 호출 상한
- 도구: @tool 함수, ToolRuntime, 승인 대기열, MCP 클라이언트
- 출력: response_model·구조화 출력, 화면 렌더링(innerHTML 등), 로그·트레이싱 설정

규칙:
- 해당 코드가 없으면 "해당 없음"이라고 쓰고 이유를 한 줄로.
- 방어가 있다고 쓰려면 그 방어 코드의 파일:줄을 반드시 적는다. 못 찾으면 "확인 못 함".
- 추측은 "(추측)"이라고 표시한다.
- 범위: {범위_폴더} 아래만 본다. {제외_폴더}는 보지 않는다.
- 마지막에 "없음/부족" 칸이 있는 항목을 위험이 큰 순서로 3개만 고른다.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{범위_폴더}` | `samples/lab-app-py/labcore`, `samples/lab-app-py/shopbot` |
| `{제외_폴더}` | `.venv`, `tests`, `eval-kit`, `attack-kit` |

## 기대 출력 예

1장 표 1.5(랩 정답)와 같은 모양이면 된다. 줄 번호는 실행할 때마다 직접 확인한다.

```text
| LLM01 | Prompt Injection | shopbot/web/chat.py:guard_input | labcore/injection/__init__.py:InputGuard.check | 단어 목록식 아님(좋음). RAG 경로는 IngestionScanner 따로 확인 | tests/attack/test_prompt_injection.py / injection·indirect |
| LLM04 | Data and Model Poisoning | 해당 없음 | - | 모델 학습·미세 조정 코드 없음 | - |
| LLM10 | Unbounded Consumption | shopbot/web/rate_limit.py:rate_limited_user | rate_limit.py, agent/middleware.py:TokenBudgetMiddleware | 비용 경보는 metrics.py까지만, 알림 연결은 확인 못 함 | test_rate_limit.py·test_token_budget.py / 평가 키트 범위 밖 |
...
위험 큰 순서 3개: (내 프로젝트 결과)
```

## 주의

- 항목 이름은 2025판 기준이다. 녹화·적용 전 [genai.owasp.org](https://genai.owasp.org/llm-top-10/)에서 새 판이 있는지 확인한다.
- Claude가 "방어 있음"이라고 해도 파일:줄을 직접 열어 확인한다. 이 표는 초안이다.
- 랩에서는 `LAB_PROFILES=before`가 방어를 모두 끈 상태다. 표를 만들 때는 기본 프로필(`shopbot/profiles/default.yaml`) 기준으로 읽게 한다.
