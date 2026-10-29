# 프롬프트: 사용자별 레이트 리밋 + 토큰 한도 붙이기

- **쓰는 곳:** 8장 8.1~8.3, 수업 4-3·4-4
- **도구:** Claude Code
- **목적:** "횟수"(레이트 리밋)와 "양"(토큰 한도)을 둘 다 막는 코드를 내 FastAPI·LangChain 프로젝트에 붙이고 pytest로 증명한다.

## 프롬프트 본문

```text
LLM을 부르는 엔드포인트 {엔드포인트_목록} 에 비용 방어를 넣어라.

1. 레이트 리밋: FastAPI 의존성 {리밋_의존성}. 키 = 로그인 사용자 ID("user:<id>"). IP 주소로 키를 잡지 않는다
   (slowapi 를 쓴다면 key_func 를 사용자 ID로 바꾼다). {횟수}/{기간}.
   넘으면 429 + Retry-After 헤더 + {"error":"RATE_LIMITED","retryAfterSeconds":N}. 로그인 의존성 뒤, 입력 검사 앞에서 돈다.
   토큰 버킷은 순수 Python 클래스로 만들고 시계(clock_ns)를 주입해 테스트가 실제 시간에 좌우되지 않게.
2. 토큰 한도: 요청당 입력 {요청당}, 사용자 하루 {사용자_하루}, 테넌트 하루 {테넌트_하루}, 전체 하루 {전체_하루}.
   LangChain 미들웨어 wrap_model_call 에서 모델을 부르기 "전에" 예상 토큰으로 검사(넘으면 모델 호출 없이 429 TOKEN_BUDGET + 남은 양),
   부른 "뒤에" AIMessage.usage_metadata(input_tokens·output_tokens) 실제 값을 사용자·테넌트별 장부에 누적.
   도구 루프마다 모델을 다시 부르므로 검사는 요청당 한 번이 아니라 모델 호출마다 돈다.
3. 설정: 대화 창 {창}(trim_messages 또는 메시지 창 미들웨어), 최대 출력 토큰 max_tokens={최대_출력},
   SDK 재시도 ChatOpenAI(max_retries={재시도})(openai SDK 기본 2 = 시도 3번. 앞단 재시도와 곱해지는 이유를 주석으로),
   도구 호출 상한 ToolCallLimitMiddleware(run_limit={도구_상한}), 모델 호출 상한 ModelCallLimitMiddleware(run_limit={모델_상한}).
4. pytest: 50번 연속 → {횟수}번만 모델 도달, 다른 사용자는 통과, 아주 긴 입력은 모델 미도달, 30턴 대화에서 요청당 메시지 수 ≤ 창.
   TestClient 통합 테스트는 테스트마다 새 앱을 만든다(모듈 전역 버킷은 테스트 사이에 남는다).
5. 여러 서버 배포라면 공유 저장소(Redis 등)용 리미터로 바꿔야 한다는 TODO 를 남긴다(예: limits 패키지 + Redis 저장소). 연결 코드는 # 확인 필요.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{엔드포인트_목록}` | `POST /api/chat`, `POST /api/products/ask` |
| `{리밋_의존성}` | `rate_limited_user` |
| `{횟수}/{기간}` | 10 / 1분 |
| `{요청당}` / `{사용자_하루}` / `{테넌트_하루}` / `{전체_하루}` | 1,000 / 20,000 / 200,000 / 1,000,000 |
| `{창}` / `{최대_출력}` / `{재시도}` | 20 / 300 / 1 |
| `{도구_상한}` / `{모델_상한}` | 5 / 8 |

## 기대 출력 예

- 랩 정답과 같은 모양: `samples/lab-app-py/labcore/cost/__init__.py`(`UserRateLimiter`, `TokenBudget`, `Limits`, `UsageLedger`), `shopbot/web/rate_limit.py`(`rate_limited_user`, redis 프로필 `LimitsRedisLimiter`), `shopbot/agent/middleware.py`(`TokenBudgetMiddleware`, `MessageWindowMiddleware`, `TokenMeter`), `shopbot/agent/factory.py`(`ToolCallLimitMiddleware`, `ModelCallLimitMiddleware`), `shopbot/profiles/default.yaml`
- 초록이어야 할 테스트: `tests/attack/test_rate_limit.py`(2개), `tests/attack/test_token_budget.py`(2개), `tests/app/test_rate_limit_api.py::test_반복_호출은_429`
- 수정 전 빨강: `samples/lab-app-py/_실측/7-3_pytest-before-cost-authz.txt`

## 주의

- 한도 값은 예시다. 서비스마다 정한다.
- 한도에 닿은 사용자에게 남은 양과 다시 쓸 수 있는 시점을 알려 준다(정상 사용자 배려). 랩의 429 본문은 `shopbot/web/errors.py`.
- 추론 모델은 `max_tokens` 대신 `max_completion_tokens`를 쓸 수 있다(확인 필요, 부록 J).
