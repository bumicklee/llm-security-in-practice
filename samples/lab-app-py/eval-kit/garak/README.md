# garak로 실습 앱 훑어보기 (18장, 수업 11-5·11-6)

garak은 NVIDIA가 관리하는 LLM 취약점 스캐너다(Apache-2.0). 우리 앱은 OpenAI 호환 서버가 아니라 챗봇 API이므로 **REST 생성기**(`rest.RestGenerator`)로 붙인다.

## 요구 버전 (2026-10-27 확인)

- **garak 0.17.1**(PyPI 2026-10-16). `requires-python >=3.11`이다. **Python 3.11 이상**이 필요하다(3.10에서는 설치가 실패한다. 3.10은 2026-10 지원 종료).
- 녹화·수강 화면을 맞추려고 버전을 고정한다. 녹화 직전에 한 번 더 올린다. 최신은 `pip install -U garak`.

## 실행 순서 (작성자 실측 2026-10-29: `_실측/11-6_garak-gptoss.txt` — 11-6)

1. shop-bot-py를 eval 프로필로 띄운다(lab-app-py 폴더, .venv 켠 상태): `python -I tools/fake_llm.py &` → `LAB_PROFILES=eval uvicorn shopbot.main:app --host 127.0.0.1 --port 8080`
2. 가상 환경을 따로 만들고 garak을 설치한다(이 키트는 garak 없이도 돈다).
   ```bash
   python3.11 -m venv .venv-garak && . .venv-garak/bin/activate    # 3.12·3.13도 된다. 버전을 붙여 만든다
   pip install garak==0.17.1
   ```
3. 쓸 프로브 이름을 고른다: `python -m garak --list_probes`
4. 내 앱 대상으로만 실행한다.
   ```bash
   python -m garak --target_type rest -G garak/rest-generator.example.json --spec probes.<프로브 이름>
   ```
   CLI(0.17.1): `--target_type`이 기본 이름, `--model_type`은 같은 뜻의 옛 이름. `--probes`는 "DEPRECATED, use --spec".

## 설정 파일(`rest-generator.example.json`) 설명

공식 예와 같은 모양으로, 주석 키 없이 둔다(05 A F9: 최상위 `_comment` 키가 무시되는지는 실행으로 확인하지 못했다).

| 키 | 값 | 메모 |
| --- | --- | --- |
| `rest.RestGenerator.uri` | `http://127.0.0.1:8080/api/chat` | 127.0.0.1만 |
| `headers.Authorization` | `Basic …`(alice:FAKE-pass-0000) | 랩 가짜 계정 |
| `req_template_json_object` | `{"message": "$INPUT"}` | shop-bot `POST /api/chat` 본문 |
| `response_json` / `response_json_field` | `true` / `answer` | `BotReply.answer`. `$`로 시작하면 JSONPath로 읽는다 |
| `request_timeout` | 60 | 기본값 20 |

키 이름은 **확인함(garak 0.17.1)**: `name`·`uri`·`method`·`headers`·`req_template_json_object`·`response_json`·`response_json_field`·`request_timeout`이 모두 v0.17.1 `garak/generators/rest.py`에 있고, `{"rest": {"RestGenerator": {…}}}` 중첩도 공식 예와 같다(05 A F8).

## 안전 규칙

- 대상 주소는 `127.0.0.1`만. 남의 서비스·공개 챗봇에 돌리지 않는다.
- garak 보고서(JSONL)에는 프로브가 보낸 **원문**이 들어 있다. 저장소에 커밋하지 않고(`.gitignore`), 녹화 화면에는 **요약 수치만** 보인다.
- 가짜 LLM은 garak 프로브 문구를 알아보지 못한다(자리표시 표식만 안다). 가짜 LLM에서 garak 결과는 "연결이 된다"는 확인일 뿐이다. 의미 있는 결과는 lmstudio 프로필(로컬 모델)에서만 나온다.
- 작성자 실측(LM Studio 0.4.26, gpt-oss-20b, 네 계열 14개 프로브 · 프로브마다 최대 10개 · `--generations 1`): 뚫림 수정 전 87/298 → 수정 후 5/300. 수정 후 300회 중 182회는 입력 가드가 막았다. 판정기는 `answer` 글만 본다(18장 18.4).

## 우리 보고서와 나란히 보기

| 질문 | garak | evalkit(이 키트) |
| --- | --- | --- |
| 무엇을 시험하나 | 넓은 범위의 일반 프로브 | 내 기능에 맞춘 50개(카나리·세션 교차·도구 기록·테넌트) |
| 도구 호출 판정 | 답 문자열 중심 | `trace.tool_calls`로 판정 |
| 배포 막기 | 직접 연결해야 함 | `--gate` 종료 코드 + 기준선 |
| 언제 쓰나 | 출시 전 한 번 넓게 훑기 | PR마다·출시 전마다 |
