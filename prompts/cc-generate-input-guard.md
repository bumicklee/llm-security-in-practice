# 프롬프트: 입력 검사 의존성(FastAPI) 만들기

- **쓰는 곳:** 4장 4.2~4.3, 수업 2-4·2-5
- **도구:** Claude Code
- **목적:** 내 프로젝트에 "길이·문자·형식"만 보는 입력 검사와 그 테스트를 만들게 한다. 검사는 에이전트 **바깥**(FastAPI 의존성)에서 모델 호출 전에 돈다. 단어 목록식 차단은 만들지 않는다.

## 프롬프트 본문

```text
FastAPI {fastapi_버전} + LangChain {langchain_버전} 프로젝트의 채팅 엔드포인트 {엔드포인트} 에 입력 검사를 추가해라.

요구사항:
1. 검사 로직은 FastAPI·LangChain에 의존하지 않는 순수 Python 클래스 {검사_클래스} 로 만든다.
   - 빈 입력 거부, {최대_글자}자 초과 거부, 제어 문자·폭 0 문자 거부
   - 줄 머리의 역할 표시 흉내(system:, assistant:, developer:, tool:)와 <|...|> 모양은 "의심"으로 표시만 하고 통과
   - 결과는 frozen dataclass(allowed, suspicious, reason)
   - 특정 공격 문장·단어 목록으로 막지 않는다
2. FastAPI 의존성 함수 {의존성_함수}(req, user=Depends(로그인 의존성)): 거부면 예외 {예외_클래스}(모델 호출 안 함),
   의심이면 요청 ID·사용자 ID·사유·길이만 기록(원문 기록 금지). 엔드포인트는 user=Depends({의존성_함수}) 로 받는다.
3. app.add_exception_handler 로 예외를 400 {"error":"INPUT_REJECTED","reason":...} 로 바꾼다.
   요청 모델(Pydantic)의 max_length 는 넉넉히 둔다. 짧게 두면 Pydantic이 먼저 422를 내서 계약(400)과 달라진다.
4. 미들웨어로도 막고 싶다면 before_agent(요청당 한 번)에 둔다. before_model 은 도구 루프마다 다시 돈다는 점을 주석으로 남긴다.
5. pytest: 정상 질문 통과, {최대_글자}+1자 거부(400), 폭 0 문자 거부, 역할 흉내는 통과+의심, 거부 시 모델 호출 0회.
   앱 테스트는 TestClient + 가짜 채팅 모델(키·네트워크 없이)로, 테스트마다 새 앱을 만든다.
   공격 입력이 필요하면 "[ATTACK-INJ-02: 역할 바꾸기 유형]" 같은 자리 표시만 쓴다.
6. 바뀐 부분만 diff 로 보여 준다.
LangChain API 이름이 확실하지 않으면 코드에 # 확인 필요 주석을 단다.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{fastapi_버전}` / `{langchain_버전}` | 0.162.0 / 1.4.7 (부록 C) |
| `{엔드포인트}` | `POST /api/chat` (`shopbot/web/chat.py`) |
| `{검사_클래스}` | `InputGuard` |
| `{의존성_함수}` | `guard_input` |
| `{예외_클래스}` | `InputRejected` |
| `{최대_글자}` | 1000 |

## 기대 출력 예

- 새 파일·함수: `InputGuard`·`GuardResult`(순수 Python), `guard_input` 의존성, `InputRejected` + 예외 처리기, 테스트 파일
- 랩 정답과 비교: `samples/lab-app-py/labcore/injection/__init__.py`(`InputGuard`, `GuardResult`, `SuspiciousInputLog`), `shopbot/web/chat.py`(`guard_input`), `shopbot/web/errors.py`(`input_rejected_handler`), 비교용 미들웨어 `shopbot/agent/middleware.py`(`InputGuardMiddleware.before_agent`)
- 지키는 테스트: `tests/attack/test_prompt_injection.py::test_긴_입력은_앞단에서_거절`, `tests/app/test_shopbot_security.py::test_긴_입력은_400`, `tests/unit/test_injection.py::test_입력_경계`

```text
$ python -m pytest tests/unit/test_injection.py tests/attack/test_prompt_injection.py -q
(초록) — 4,000자 입력은 400 INPUT_REJECTED, 모델 호출 0회
```

## 주의

- 단어 목록(블랙리스트)이 생성되면 지운다. 변형하면 금방 뚫리고, 정상 사용자를 막는다.
- 의심 기록에 원문을 남기는 코드가 생기면 고친다(4장 4.5, 11장 11.4).
- 검사를 LangChain 미들웨어에만 두면 도구 없이 모델을 부르는 다른 경로(상품 Q&A 등)가 빠지기 쉽다. 엔드포인트마다 의존성을 거는 쪽이 빠뜨리기 어렵다(랩은 `/api/products/ask`에도 `guard_question`).
