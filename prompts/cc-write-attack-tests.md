# 프롬프트: 가짜 LLM으로 결정적인 공격 테스트 쓰기(pytest)

- **쓰는 곳:** 12장 12.2~12.3, 수업 7-2·7-3 · 22장 22.4, 수업 14-3
- **도구:** Claude Code (같은 규칙을 스킬로 묶은 것: `../skills/llm-attack-tests/SKILL.md`)
- **목적:** "모델이 공격에 넘어간 답을 돌려줘도 우리 코드가 막는가"를 pytest로 증명하는 테스트를 만든다.

## 프롬프트 본문

```text
{대상_폴더} 에 공격 테스트를 추가해라.

원칙:
- 진짜 모델 호출 금지. 가짜 채팅 모델(langchain_core BaseChatModel 하위 클래스, 또는 순수 Python 가짜 LLM 클라이언트)을 만들어,
  자리 표시 [ATTACK-INJ-…] 를 보면 시스템 프롬프트를 그대로 읊는 등 "일부러 넘어간" 답을 돌려준다.
  구조화 출력(response_format/json_schema)을 요청받으면 JSON으로 감싼다. 토큰 수는 고정 규칙(글자 3개 = 1토큰)으로 usage_metadata에 넣는다.
- 공격 입력은 자리 표시만: "[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]" 형식. 실제 공격 문장은 쓰지 않는다.
- 테스트는 "막혀야 한다"는 계약만 적는다. 같은 테스트를 수정 전 구현에 돌리면 실패해야 한다
  ({전환_옵션} 로 구현 선택. conftest.py 의 pytest_addoption 으로 만든다).
- 과잉 차단 테스트도 하나씩: 정상 질문은 통과.
- FastAPI 통합 테스트는 TestClient + 앱 팩토리(create_app(settings))로 테스트마다 새 앱을 만들고,
  채팅 모델 의존성은 app.dependency_overrides[모델 의존성] = lambda: 가짜 모델 로 바꾼다.
- 시간·DNS·HTTP 는 주입한다(시계 함수, 가짜 해석기, 가짜 웹 클라이언트). 비동기 테스트는 anyio 플러그인.

만들 테스트:
{테스트_목록}

테스트 함수 이름은 한국어로 써도 된다(예: test_bob은_alice의_주문을_취소할_수_없다). 각 테스트 위에 주석: 목적 / 막는 코드 위치 / 대응 장.
끝나면 {테스트_명령} 결과 마지막 줄과, {전환_옵션}=before 로 돌린 실패 수를 보여 줘.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{대상_폴더}` | `tests/attack` |
| `{전환_옵션}` | `--lab-target` (`tests/conftest.py`) |
| `{테스트_목록}` | `test_prompt_injection.py`(비밀 미유출·긴 입력 거절·정상 통과), `test_tenant_isolation.py`, `test_rate_limit.py`, `test_tool_authorization.py`, `test_ssrf.py` |
| `{테스트_명령}` | `python -m pytest tests/attack tests/unit -q` |

## 기대 출력 예

랩 실측(`samples/lab-app-py/_실측/1-2_pytest-count.txt`, `12-4_pytest-before.txt`):

```text
$ python -m pytest tests/attack tests/unit -q
49 passed
$ python -m pytest tests/attack tests/unit --lab-target=before -q --tb=no
23 failed, 26 passed
```

랩 정답: 가짜 채팅 모델 `tests/app/stub_model.py`(`StubChatModel`), 가짜 LLM `labcore/llm/__init__.py`(`ScriptedFakeLlm`), 조립기 `tests/attack/lab.py`(`before()`이면 수정 전 구현), 앱 테스트 `tests/app/conftest.py`(`make_client`: `create_app(load_settings(...))` + `dependency_overrides[get_chat_model]`).

## 주의

- 실제 모델 통과율은 이 테스트가 아니다(12.5, 17장). 단위 테스트에 "확률적으로 통과" 같은 재시도·임계값을 넣지 않는다.
- 생성된 테스트가 가짜 LLM 응답 문자열을 그대로 비교만 한다면(우리 코드를 안 지남) 의미 없다. 반드시 방어 코드를 거치게 한다. `--lab-target=before`에서 **빨강이 되는지** 꼭 본다.
- 모듈 전역에 버킷·장부를 두면 테스트 사이에 상태가 남는다(12.3). 앱 팩토리로 테스트마다 새로 만든다.
