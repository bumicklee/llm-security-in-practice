# 프롬프트: 출력 처리·마스킹·로그·트레이싱 점검

- **쓰는 곳:** 11장 11.1~11.5, 수업 6-1~6-5
- **도구:** Claude Code
- **목적:** 모델 답이 화면·로그·저장소로 흘러가는 길을 모두 찾아 이스케이프·마스킹·보관 기간·원문 로그·트레이싱 여부를 점검한다.

## 프롬프트 본문

```text
이 프로젝트에서 모델 응답(AIMessage.content, structured_response, with_structured_output 결과)과 사용자 메시지가 흘러가는 곳을 모두 찾아라. 코드는 고치지 마라.

1. 화면: innerHTML / dangerouslySetInnerHTML / v-html / 템플릿의 |safe / 마크다운 렌더러 사용 위치, 이스케이프 여부
2. 모델로 보내기 전: 사용자 메시지·검색 문서에 전화번호·이메일·키 모양 마스킹이 있나(미들웨어 before_model 인지, 도구 결과도 지나는지)
3. 저장: 대화 기록(체크포인터·DB) 저장 위치, 저장 항목, 마스킹 여부, 보관 기간·삭제 작업
4. 로그: logging 으로 프롬프트·응답 원문을 찍는 곳, langchain_core.globals.set_debug(True)·set_verbose(True),
   트레이싱 환경 변수(LANGSMITH_TRACING·LANGSMITH_TRACING_V2·LANGCHAIN_TRACING·LANGCHAIN_TRACING_V2)를 켜는 설정 파일·compose·CI,
   그리고 이 값이 켜져 있으면 앱이 시작을 거부하는 검사(fail closed)가 있는지. .env 파일은 열지 않는다.
5. 감사: 요청 ID 하나(X-Request-Id, contextvars)로 질문·검색 문서·도구 호출·승인·답을 이을 수 있나
표: 위치 | 무엇이 흐르나 | 지금 처리 | 문제 | 제안
제안에는 "남길 것 / 가릴 것 / 남기지 말 것" 중 무엇인지 표시.
```

## 입력 예

- 대상: `samples/lab-app-py/shopbot`, `samples/lab-app-py/labcore/output`, `samples/lab-app-py/labcore/audit`

## 기대 출력 예

```text
| shopbot/static/app.js | 봇 답 | flags.outputEscape=true면 textContent | 없음 | - |
| shopbot/agent/middleware.py:PiiMaskMiddleware.before_model | 사용자 메시지 | PiiMasker.mask, 체크포인터 앞 | 없음 | 가릴 것 |
| shopbot/web/chat.py:chat | audit.question / audit.answer | 마스킹 후 기록 | 없음 | 남길 것(마스킹본) |
| shopbot/main.py:check_prompt_logging | 트레이싱 변수·set_debug | 기본·eval 프로필은 시작 거부, before는 경고 | 없음 | 남기지 말 것 |
```

트레이싱 변수를 켠 채 시작하면 거부되는 장면은 `samples/lab-app-py/_실측/6-5_tracing-refuse.txt`(uvicorn 종료 코드 3, `PromptLoggingRefused`), 감사 로그는 `_실측/6-4_audit-jsonl.txt`.

## 주의

- 법적 보관 기간은 서비스·업종마다 다르다. 이 프롬프트의 답은 법률 자문이 아니다. 원문(관련 법령·사내 규정)을 확인한다.
- 디버깅 중 `set_debug(True)`나 트레이싱을 켰다면 끈 뒤 그동안 쌓인 로그·외부 기록을 지운다.
- 트레이싱 변수 이름은 랩이 확인한 langsmith 0.14.14 소스 기준이다. 버전이 바뀌면 공식 문서로 다시 확인한다(부록 J).
- LangChain `PIIMiddleware`는 비교로만 본다. 기본 탐지기 목록에 한국 전화번호 형식이 있는지는 확인 필요(11장).
