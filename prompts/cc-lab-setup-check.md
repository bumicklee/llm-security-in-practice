# 프롬프트: 랩 설치 점검(포트 바인딩·가짜 값·잠금 파일·pytest)

- **쓰는 곳:** 2장 2.1·2.5, 수업 1-6~1-8
- **도구:** Claude Code
- **목적:** 랩이 127.0.0.1에만 열려 있고, 가짜 값만 쓰고, 잠금 파일 기준 버전과 맞는지, 테스트가 초록인지 한 번에 점검한다.

## 프롬프트 본문

```text
{랩_폴더} 를 점검해라. 파일은 고치지 말고 결과만 표로 보고해라.

1) docker-compose.yml 의 모든 ports 항목이 "127.0.0.1:" 로 시작하는가? 아니면 줄 번호.
2) sk- 로 시작하는 키 모양이 들어 있는 파일 이름만 찾아라(값은 찍지 않는다): grep -rlE "\bsk-[A-Za-z0-9_-]{6,}" --include='*.py' --include='*.yaml' --include='*.json' --exclude-dir=.venv --exclude-dir=results --exclude-dir=private --exclude='.env*' . — .env 파일과 eval-kit/private/ 는 열지도 훑지도 않는다. 나온 파일마다 키 모양이 FAKE 가 들어간 가짜 값뿐인지 보고, FAKE 가 없는 키 모양은 값 대신 파일 이름과 개수만 적는다.
3) shopbot/profiles/default.yaml 의 llm_base_url·mgmt_host 값, 그리고 uvicorn 실행 예(README, compose)의 --host 값이 127.0.0.1 인가? (컨테이너 안의 0.0.0.0은 compose 포트가 127.0.0.1: 로 묶여 있으면 OK)
4) requirements.lock 의 {기준_패키지} 버전이 {기준_버전} 과 같은가? 지금 venv 의 python --version 은 3.11 이상인가?
5) attack-kit/*.sh 가 모두 _loopback.sh 의 require_loopback 을 부르는가? run_attacks.py·mcp_tool_review.py 도 127.0.0.1 밖을 거부하는가?
6) 아래 명령을 실행하고 마지막 줄만 보여 줘: {테스트_명령}

각 항목: 결과(OK/문제) | 근거(파일:줄 또는 명령 출력) | 고칠 방법(문제일 때만)
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{랩_폴더}` | `samples/lab-app-py` |
| `{기준_패키지}` | `fastapi`, `langchain`, `langchain-openai`, `openai`, `mcp`, `pytest` |
| `{기준_버전}` | 부록 C 고정 버전 표(예: fastapi 0.162.0, langchain 1.4.7, langchain-openai 1.7.3, openai 3.40.0, mcp 2.3.0) |
| `{테스트_명령}` | `python -m pytest -q` (venv를 켠 상태) |

## 기대 출력 예

6번 줄은 랩 실측(`samples/lab-app-py/_실측/1-2_pytest-count.txt`)과 같은 모양이다. 1~5번의 줄 번호는 실행할 때 직접 확인한다.

```text
| 1 | OK | docker-compose.yml: ports 모두 "127.0.0.1:" |
| 2 | OK | FAKE 아닌 키 모양 0건 |
| 3 | OK | default.yaml llm_base_url http://127.0.0.1:8070/v1, mgmt_host 127.0.0.1 |
| 4 | OK | requirements.lock = 부록 C 표, Python 3.14.6 |
| 5 | OK | flood.sh·run-attacks.sh·wobble.sh → require_loopback |
| 6 | OK | 61 passed, 19 deselected in 1.48s |
```

## 주의

- 6번은 pytest를 실제로 돌린다. Claude Code가 명령 실행 허락을 물으면 내용 확인 후 허락한다(`../skills/settings/settings.example.json`은 `python -m pytest *`를 allow에 둔다).
- "문제"가 나오면 Claude에게 바로 고치게 하지 말고, 근거 줄을 먼저 직접 연다.
- 버전 표의 기준은 부록 C다. 이 프롬프트의 예시 숫자와 부록 C가 다르면 부록 C를 따른다.
