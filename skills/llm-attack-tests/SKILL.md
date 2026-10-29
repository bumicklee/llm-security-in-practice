---
name: llm-attack-tests
description: FastAPI + LangChain 프로젝트에 가짜 채팅 모델(BaseChatModel)·가짜 LLM을 써서 결정적으로 도는 pytest 공격 테스트(프롬프트 인젝션·RAG 간접 인젝션·테넌트 격리·레이트 리밋·토큰 한도·도구 권한·SSRF·출력 처리)를 만든다. 공격 입력은 자리 표시만 쓴다. 공격 테스트 작성, 방어 코드를 증명하는 테스트 요청 시 쓴다.
argument-hint: "[테스트 폴더] [구멍: injection|rag|tenant|rate|budget|tool|ssrf|output]"
---

# LLM 공격 테스트 만들기 (pytest)

목표: "모델이 공격에 넘어간 답을 돌려줘도 **우리 코드가** 막는다"를 pytest로 증명한다. 실제 모델·외부 API를 부르지 않는다. 인자: `$ARGUMENTS`.

## 절차

1. **방어 코드 위치 찾기.** 입력 검사 의존성(`Depends`)·미들웨어(`before_agent`·`before_model`·`wrap_model_call`), 출력 스키마(`response_format`·`with_structured_output`)와 출력 정책, 검색 진입점과 필터, 레이트 리밋 의존성, 토큰 한도, `@tool` 함수와 `ToolRuntime`, URL 가져오기, 렌더링·로그 코드를 찾아 목록으로 보여 준다. 없으면 "방어 없음 — 테스트는 실패할 것"이라고 먼저 알린다.
2. **가짜 모델 만들기.** 테스트 폴더에 둔다. 두 가지 중 프로젝트 구조에 맞는 것:
   - `langchain_core.language_models.BaseChatModel` 하위 클래스 `StubChatModel` — `create_agent`·`with_structured_output`을 그대로 지나게 한다.
   - 방어 부품이 순수 Python이면 `call(request) -> response`만 있는 가짜 LLM 클라이언트.
   규칙:
   - 사용자 메시지에 `[ATTACK-INJ-`가 있으면 시스템 프롬프트를 그대로 답한다(일부러 넘어감)
   - 프롬프트 안 문서에 `[ATTACK-RAG-`가 있으면 허용 목록 밖 가짜 링크(`http://127.0.0.1:9999/fake`)를 답한다
   - `[ATTACK-OUT-`이 있으면 `data-lab-attack` 속성이 붙은 태그 자리 표시를 답에 섞는다
   - 구조화 출력(`response_format`/json_schema)을 요청받으면 JSON으로 감싼다
   - 토큰 수는 고정 규칙(예: 글자 3개 = 1토큰)으로 `usage_metadata`에 넣는다
   - 도구는 부르지 않는다. 도구 권한은 도구 함수(또는 그 아래 순수 Python 부품)를 직접 불러 시험한다
3. **테스트 쓰기.** 파일마다 한 구멍: `test_prompt_injection.py`, `test_indirect_injection.py`, `test_tenant_isolation.py`, `test_rate_limit.py`, `test_token_budget.py`, `test_cache_isolation.py`, `test_tool_authorization.py`, `test_ssrf.py`, `test_output_and_log.py`. 각 파일에 **정상 사용자 통과** 테스트를 하나씩 넣어 과잉 차단을 잡는다. 함수 이름은 한국어로 써도 된다(`test_bob은_alice의_주문을_취소할_수_없다`). 각 테스트 위에 주석: 목적 / 막는 코드 위치 / 대응 장.
4. **수정 전/후 전환.** `conftest.py`의 `pytest_addoption`으로 `--lab-target=before|after` 같은 옵션을 만들고, 조립 함수 하나가 옵션에 따라 수정 전/후 구현을 준다. 테스트 본문은 두 경우 모두 같다(계약만 적는다).
5. **FastAPI 통합 테스트.** `TestClient` + 앱 팩토리로 **테스트마다 새 앱**을 만든다(모듈 전역 버킷·장부는 테스트 사이에 남는다). 채팅 모델 의존성은 `app.dependency_overrides[모델 의존성] = lambda: stub`으로 바꾼다. 로그인은 가짜 계정(HTTP Basic 등).
6. **빨강 확인.** 방어를 끈 상태(`--lab-target=before` 또는 설정 스위치)에서 테스트가 실패하는지 보여 준다. 실패하지 않으면 테스트가 방어 코드를 안 지나는 것이므로 고친다.
7. **초록 확인.** 방어를 켠 상태에서 통과. 사용자 허락을 받고 `python -m pytest <테스트 폴더> -q`를 실행해 마지막 줄을 보여 준다.
8. **CI 제안.** `.github/workflows/`에 PR마다 pytest를 도는 잡을 제안한다(비밀값·네트워크 모델 없이 돌아야 한다. 잠금 파일 `--require-hashes` 설치).

## 규칙

- 공격 입력은 `[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]`처럼 **범주 + 자리 표시**만. 실제 인젝션·탈옥 문구, 실제 XSS 페이로드를 쓰지 않는다. ID는 프로젝트의 공격 유형 등록부(랩: `attack-registry.yaml`)에 있는 것만.
- 네트워크가 필요한 검사(SSRF)는 DNS 해석기·HTTP 클라이언트를 생성자 인자로 빼서 가짜로 바꾼다. 공인 IP 예시는 문서용 대역(203.0.113.0/24)만.
- 시간에 좌우되는 검사(레이트 리밋)는 시계 함수(예: `clock_ns`)를 주입한다. `time.sleep`으로 기다리지 않는다.
- 테스트에 재시도·확률 임계값을 넣지 않는다. 결정적이어야 한다. 실제 모델 통과율은 별도 평가(교재 17장, 평가 키트)로 한다.
- 비동기 테스트는 anyio 플러그인(`@pytest.mark.anyio`)을 쓴다.
- LangChain API 이름이 확실하지 않으면 `# 확인 필요` 주석을 남긴다(기준: 부록 C 고정 버전).

## 참고

- 랩 정답: `samples/lab-app-py/tests/attack/`(조립기 `lab.py`, 전환 `--lab-target=before`), `tests/app/stub_model.py`(`StubChatModel`), `tests/app/conftest.py`(`make_client`), `tests/conftest.py`(`pytest_addoption`), 가짜 LLM `labcore/llm/__init__.py`(`ScriptedFakeLlm`)
- 랩 숫자: `pytest tests/attack tests/unit` 49개 초록, `--lab-target=before`면 23개 빨강(`_실측/1-2_pytest-count.txt`, `12-4_pytest-before.txt`)
- 프롬프트판: `prompts/cc-write-attack-tests.md`
