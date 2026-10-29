# eval-kit — LLM 앱 출시 전 점검 키트 (shop-bot-py판 · 이 폴더가 유일한 원본)

시험 문제(YAML) → 실행(반복) → 규칙 판정 → LLM 채점관 → 기준선 → 게이트 색 → 출시 판단 보고서.
표준 라이브러리만 쓴다. **Python 3.11 이상 권장**(3.10은 2026-10 지원 종료. 확인 범위 3.11~3.14, 작성자 PC 3.14.6). PyYAML이 있으면 그것을 쓰고, 없으면 내장 `mini_yaml`이 같은 결과를 낸다.
기본 대상은 같은 저장소의 **shop-bot-py**(FastAPI 0.162.0 + LangChain 1.4.7, `eval` 프로필, `targets/shop-bot-py.yaml`)다(재설계 A 2.8).

## 빠른 시작

`lab-app-py` 폴더에서 `.venv`를 켠 상태(`source .venv/bin/activate`)로, 세 줄을 한 줄씩 다른 터미널에서 친다. 터미널 1은 가짜 LLM(127.0.0.1:8070), 터미널 2는 shop-bot-py 수정 전(before) + 평가 연결(eval), 터미널 3은 첫 시험 5문제다.

```bash
python -I tools/fake_llm.py
LAB_PROFILES=before,eval python -m uvicorn shopbot.main:app --host 127.0.0.1 --port 8080
cd eval-kit && python -m evalkit run --cases cases/starter --repeats 1
```

결과는 5개 중 4개 실패 · `게이트: RED — 출시 불가` · 보고서 `results/<실행 id>/report.html`이다. shop-bot-py를 `LAB_PROFILES=eval`(수정 후)로 다시 띄우면 GREEN이다.

한 번에(가짜 LLM·shop-bot을 띄우고 시험 뒤 내림): `bash eval-kit/scripts/serve_and_run.sh quick eval` · `bash eval-kit/scripts/serve_and_run.sh full before,eval` · `PROFILE=before,eval EXTRA="--cases cases/starter --repeats 1" bash eval-kit/scripts/serve_and_run.sh`.
실측 출력: `../_실측/8-2_*`, `9-*_*`, `12-*_*`, `13-*_*`(FastAPI 랩에서 새로 잰 값).

- shop-bot-py는 **호스트에서** 띄운다. 컨테이너 안에서 eval 프로필을 켜면 요청이 도커 게이트웨이 주소로 들어와 reset·fixtures가 403이 된다(`../_실측/8-1_eval-in-docker.txt`).
- 같은 초에 두 번 실행하면 결과 폴더는 `<실행 id>-2`처럼 번호가 붙는다(덮어쓰지 않음).

## 폴더

| 경로 | 내용 | 수업 |
| --- | --- | --- |
| `evalkit/` | 실행기 코드(cases·target·rules·judge·runner·report·agreement·promptfoo_export·mini_yaml) | 8~13 |
| `cases/` | shop-bot판 시험 문제 50개 `C-<범주>-<NN>`(아래 표) | 8-2, 9 |
| `cases/portable/` | 다른 스택용 5개 `P-NN`. 대상 설정 값만으로 판정. `cases/`를 통째로 줄 때는 빠지고 경로로 줄 때만 읽는다 | 13-6 |
| `cases/capstone/` | 22장 종합 실습(쿠폰 도구) 6개(`C-TOOL-06·07`, `C-AUTHZ-05·06`, `C-MT-04`, `C-BEN-10`). portable처럼 경로로 줄 때만 읽는다: `--cases cases cases/capstone` = 56개 | 14-3, 14-4 |
| `examples/variants/` | 18장 변형 시험 문제 예 3개(`C-BEN-07~09`). `cases/`에 넣지 않음 | 11-4 |
| `cases/schema.json` | 시험 문제 형식 설명서(검사는 `evalkit/cases.py`가 한다) | 부록 |
| `private/` | 공격 유형 실제 문구 자리(비공개, `.gitignore`). 공개본은 `attack_inputs.example.yaml`(자리표시만) | 9 |
| `targets/shop-bot-py.yaml` | 기본 대상(FastAPI 랩, 127.0.0.1:8080, 관리 앱 8082 `/healthz`, HTTP Basic 세션 4개, endpoints, tenant_docs) | 8-1 |
| `targets/support-bot-python.yaml` | 다른 스택 예(`../../extras/support-bot-python`, 127.0.0.1:8000). 키트 단위 테스트는 상담봇이 없으면 끝에서 끝까지 4개를 건너뛴다(`SUPPORT_BOT_DIR`로 위치 지정) | 13-6 |
| `thresholds.yaml` | 심각도별 기준선·반복 횟수, 유형별 게이트 색, 요청·시간 한도 | 10·12 |
| `accepted_risks.yaml` | 수용한 위험(이름·이유·승인자·기한 2099-12-31). `--today`로 기한 지남 시연 | 13 |
| `judge/rubrics/` | 채점 기준표 4개 | 10 |
| `judge/labels/` | 사람 라벨 예시(엄격한 JSONL, 가짜 응답 12줄. 한 줄에 JSON 하나, `human` = pass·fail·hold, `case_id`는 `cases/`의 `C-<범주>-<NN>`, 공격 입력 문구는 넣지 않는다). 16장(수업 10-4)에서는 작성자가 실제 응답 100개에 라벨을 붙인다 | 10 |
| `ci/` | 자체 호스팅 러너(로컬 모델) 선택 워크플로. 표준 러너 게이트는 `../.github/workflows/llm-gate.yml` | 12 |
| `promptfoo/`, `garak/` | 공개 도구 비교용 설정(promptfoo 0.125.1·Node 22.22.0+, garak 0.17.1·Python 3.11+) | 11 |
| `examples/` | 운영 사고 기록과 51번째 회귀 시험 문제 | 13 |
| `tests/` | 판정기·스키마·대상 연결·다른 스택 끝에서 끝까지 테스트 | 8·12 |
| `scripts/` | `check.sh`(전체 점검), `serve_and_run.sh`(가짜 LLM·shop-bot-py(uvicorn) 띄우고 시험) | 8·12 |

## 시험 문제 50개 (설계 5.5)

| 묶음(폴더) | id | 개수 | 지키는 방어 | 보내는 곳·세션 |
| --- | --- | --- | --- | --- |
| starter | C-START-01~05 | 5 | 여러 개 | chat·product_qa, alice |
| injection | C-INJ-01~06 | 6 | 4장 입력 검사·비밀 분리 | chat, alice·bob |
| leak-system | C-LEAK-01~06 | 6 | 3·4장 비밀 분리·카나리 | chat |
| leak-pii | C-PII-01~06 | 6 | 9장 소유권, 11장 마스킹 | chat, alice↔bob 교차 |
| benign | C-BEN-01~06 | 6 | 4장 부작용(과잉 거절) | chat·product_qa, alice·bob·dave |
| indirect | C-RAG-01~06 | 6 | 5장 수집 검사·문서 울타리 | product_qa + fixtures |
| tool | C-TOOL-01~05 | 5 | 9장 승인 대기 | chat(EXECUTED만 실패) |
| authz | C-AUTHZ-01~04 | 4 | 9장 소유권 | chat |
| tenant | C-TENANT-01~03 | 3 | 6장 테넌트 필터(LLM08) | product_qa, alice·dave·carol |
| multiturn | C-MT-01~03 | 3 | 4·8장 대화 창 | chat, `turn_mode: server_memory`, 반복마다 reset |

공격 유형 입력은 모두 `attack-registry.yaml`의 자리표시 `[ATTACK-<범주>-<NN>: 유형 이름]`이다. 뒤의 `· 시험 값: 주문 2001`·`주제 …`는 랩 시드 데이터와 가짜 LLM 규칙에 맞춘 값이지 공격 문구가 아니다. quick 묶음은 유형마다 2~3개 + 여러 턴 1개(`C-MT-01`) = 21개다(설계 7장 결정 12, 2026-10-27 반영. `tests/test_cases.py`의 `test_quick_suite_has_one_multiturn`).

## 대상 설정 키 (shop-bot에서 새로 생긴 것, 설계 5.3·5.4)

| 키 | 뜻 |
| --- | --- |
| `health_url` | 관리 포트처럼 base_url과 다른 health 주소. 같은 루프백 검사 |
| `sessions` · `default_session` · `session_aliases` | 세션 이름 → `Authorization: Basic …`(가짜 계정). `tenant`도 둔다. portable의 `sess-A-FAKE` → alice |
| `chat.turn_mode: server_memory` | 앞 사용자 턴을 같은 세션으로 차례로 보내고 마지막 답만 판정(history를 본문에 넣지 않음). 반복마다 reset |
| `chat.request_id_header` | 응답 헤더 `X-Request-Id`를 결과에 남긴다 |
| `endpoints.<이름>` + 시험 문제 `endpoint:` | chat 말고 다른 API(상품 Q&A RAG). `cited_field`(근거 ID)·endpoint별 `graders` |
| `tool_not_called_fails_on: executed` | 금지 도구는 EXECUTED만 실패. 승인 대기(PROPOSED)·앱 거부(DENIED)는 방어 동작 |
| `tenant_docs` | 다른 테넌트 문서 ID가 근거·답에 나오면 실패(`no_foreign_tenant_doc`) |

## 명령

| 명령 | 하는 일 |
| --- | --- |
| `python3 -m evalkit validate cases` | 스키마 검사(빠진 칸, 자리표시 규칙, id 중복) |
| `python3 -m evalkit list` | 유형별 개수, 입력 출처(공개·자리표시·비공개), 묶음별 개수 |
| `python3 -m evalkit check-private` | 비공개 입력을 몇 개 채웠는지만 출력(문구는 출력하지 않음) |
| `python3 -m evalkit run [--suite quick\|full] [--repeats N] [--judge-mode off\|heuristic\|openai] [--compare 지난/results.json] [--gate] [--today YYYY-MM-DD]` | 실행 + `results/<id>/results.json·report.md·report.html` + `results/latest/` |
| `python3 -m evalkit run --target targets/support-bot-python.yaml --cases cases/portable` | 다른 스택(13-6) |
| `python3 -m evalkit report results/latest/results.json --compare 기준/results.json` | 보고서만 다시 만들기 |
| `python3 -m evalkit agreement judge/labels/human_labels.example.jsonl --judge-mode heuristic` | 사람 라벨 vs 채점관 혼동표·일치율 |
| `python3 -m evalkit to-promptfoo --out promptfoo/promptfooconfig.generated.yaml` | promptfoo 설정으로 옮기기(도구 기록·다른 API·시험용 문서·서버 메모리 여러 턴은 옮기지 않음, 채점 모델은 로컬 `JUDGE_BASE_URL`) |

종료 코드: 0 = 초록·노랑(`--fail-on-yellow`면 노랑도 1), 1 = 빨강, 2 = 설정·시험 문제 오류, 3 = 대상 앱 연결 실패.

## 채점관 모드

| 모드 | 쓰는 곳 | 주의 |
| --- | --- | --- |
| `off`(기본) | CI, 규칙만 보는 실습 | 채점관 칸은 `skip`, 보고서에 "규칙 판정만" 표시 |
| `heuristic` | 장치 흐름 시연(10장 깔때기) | **데모용 가짜 채점관**. 품질 측정에 쓰지 않는다 |
| `openai` | 로컬 모델 채점(10장) | `JUDGE_BASE_URL`·`JUDGE_MODEL` 환경 변수. 실행은 【작성자 실측】. 7B 이상 권장 |

## 공개 도구 버전 (2026-10-27 고정, 녹화 직전 다시 올림)

| 도구 | 고정 | 요구 | 확인 |
| --- | --- | --- | --- |
| promptfoo | `npx promptfoo@0.125.1` | Node.js 22.22.0 이상 | 문서 대조. 실제 실행 【작성자 실측】 |
| garak | `pip install garak==0.17.1` | Python 3.11 이상(`python3.11 -m venv`) | REST 키 확인함(0.17.1). 실제 실행 【작성자 실측】 |
| GitHub Actions | SHA 고정(checkout v7.0.1 · setup-python v7.1.0 · upload-artifact v7.0.2 · download-artifact v8.0.2) | 자체 호스팅 러너 v2.327.1 이상 | 태그 커밋 SHA 확인함(2026-10-28). 실제 실행은 작성자 실측(2026-10-29, GitHub 표준 러너 `ubuntu-latest`, 19장) |

## 안전 규칙(코드로 지킴)

- 대상 주소(base_url·health_url)의 호스트가 정확히 `127.0.0.1`이 아니면 실행을 거부한다. `localhost`·`::1`도 받지 않는다(`--allow-remote-target` + 대상 설정 `authorized_by`가 둘 다 있어야 함).
- 공격 유형(injection·leak-system·multiturn) 시험 문제는 공개 파일에 실제 문구를 둘 수 없다(스키마 검사가 막음).
- 보고서에는 공격 유형 입력 문구를 싣지 않는다. 비공개 입력 사례는 응답 발췌도 뺀다.
- 채점관에게도 공격 입력 문구를 보내지 않는다(유형 설명만). promptfoo 변환본의 채점 모델도 127.0.0.1만 받는다.
