# 프롬프트: LLM 기능 PR 리뷰(팀 리뷰 기준)

- **쓰는 곳:** 20장 20.5, 수업 13-3 · 21장 21.5, 수업 13-7
- **도구:** Claude Code(`gh pr diff`로 diff를 가져와 리뷰) 또는 스킬 `/llm-security-review`(`../skills/llm-security-review/SKILL.md`)
- **목적:** LLM 기능이 들어간 PR에서 꼭 볼 곳만 짚는다. 체크리스트 C01~C20(20장 표 20-1, 부록 B) 기준.

## 프롬프트 본문

```text
아래 diff 를 리뷰해라. 코드는 고치지 말고 코멘트 목록만.
{diff}

먼저 diff 에서 아래가 바뀌었는지 찾는다:
- create_agent(...)·system_prompt·middleware 목록·response_format, 시스템 프롬프트 상수
- FastAPI 의존성(Depends: 로그인·레이트 리밋·입력 검사)과 그 순서, response_model, 예외 처리기
- @tool 함수·ToolRuntime·args_schema·도구 허용 목록·승인 대기열
- 벡터 저장소 add_documents·similarity_search·filter 인자, 리트리버
- 설정 파일(프로필 YAML의 defense.*·max_tokens·max_retries·호출 상한), requirements.lock
- 로그 문장, set_debug, 트레이싱 환경 변수, 화면 렌더링(innerHTML 등)
- .github/workflows/**, eval-kit/thresholds.yaml·accepted_risks.yaml, 시험 문제(cases/**) 삭제·판정 변경

각 변경을 체크리스트 C01~C20 중 해당 항목으로 판정:
| 항목 | 파일:줄 | 판정(통과/문제/확인 필요) | 이유 | 증명할 테스트(pytest 파일::함수 또는 평가 시험 ID, 없으면 제안) |

규칙:
- "문제"는 근거 줄이 있을 때만. 추측은 "확인 필요".
- 방어를 끄는 변경(스위치 false, 한도 상향, 필터 제거, 로그 원문·트레이싱 켜기, 게이트 기준 낮추기, 시험 문제 삭제)은 맨 위에 따로 모은다.
- 공격 방법을 설명하지 않는다.
```

## 입력 예

- `{diff}` = `gh pr diff 42` 결과 또는 `git diff origin/main...HEAD` (랩 연습: `shopbot/profiles/default.yaml`에서 `ssrf_guard: false`로 바꾼 가짜 PR)

## 기대 출력 예

```text
[방어를 끄는 변경]
| C17 | shopbot/profiles/default.yaml:(ssrf_guard 줄) | 문제 | ssrf_guard: false — URL 도구가 NaiveUrlFetcher로 바뀌어 내부 주소에 닿음 | tests/attack/test_ssrf.py 는 labcore만 보므로 앱 설정 PR은 따로 확인 필요 → 앱 테스트 제안 |
[그 밖]
| C15 | shopbot/tools/orders.py:(cancel_order) | 통과 | 사용자를 ToolRuntime 컨텍스트에서 얻음 | tests/attack/test_tool_authorization.py::test_bob은_alice의_주문을_취소할_수_없다 |
```

## 주의

- 리뷰 코멘트를 PR에 자동으로 다는 것은 팀 합의 후에. 처음에는 사람이 읽고 골라 단다.
- 이 프롬프트는 [`../skills/llm-security-review/SKILL.md`](../skills/llm-security-review/SKILL.md)·[`checklist.md`](../skills/llm-security-review/checklist.md)와 같은 기준을 쓴다.
- 설정 PR(프로필 YAML)은 labcore 공격 테스트(`--lab-target`)로는 안 잡힐 수 있다. 앱 테스트(`tests/app/`)와 평가 게이트가 잡는지 함께 본다(19장 19.7).
