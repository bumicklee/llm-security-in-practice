# skills — Claude Code 스킬·설정·훅 예시 (FastAPI·LangChain)

예제·소스: https://github.com/bumicklee/llm-security-in-practice.git (이 폴더는 저장소의 `skills/`).

이 강의에서 Claude Code로 내 FastAPI·LangChain 프로젝트를 점검·보강·시험할 때 쓰는 자료다. 형식은 Claude Code 스킬 공식 형식(`SKILL.md` + YAML 앞머리)을 따랐다([skills 문서](https://code.claude.com/docs/en/skills), 2026-10-28 확인).

| 경로 | 무엇 | 쓰는 장 · 수업 | 검사 |
| --- | --- | --- | --- |
| [llm-security-review/SKILL.md](llm-security-review/SKILL.md) | 출시 전 체크리스트 C01~C20으로 읽기 전용 점검·PR 리뷰(입력 검사 의존성·출력 스키마·테넌트 필터·도구 허용 목록·승인·레이트 리밋·PII 마스킹·트레이싱 변수·훅 fail closed) | 20장 20.5·21장 21.5 · 13-3·13-7 | 앞머리 YAML 파싱 |
| [llm-security-review/checklist.md](llm-security-review/checklist.md) | 20항목 원본(20장 표 20-1·부록 B와 같음) + 스캐너 전용 C00·H01~H03 | 20장 · 13-3 | 표 20-1과 줄 대조 |
| [llm-security-review/scripts/scan.sh](llm-security-review/scripts/scan.sh) | grep으로 단서 찾기(판정 아님). 파일·네트워크 건드리지 않음, `.env` 열지 않음 | 20장 | `bash -n`, `samples/lab-app-py`에 실행 |
| [llm-attack-tests/SKILL.md](llm-attack-tests/SKILL.md) | 가짜 채팅 모델(`BaseChatModel`)·가짜 LLM으로 결정적 pytest 공격 테스트 만들기, `--lab-target=before`로 빨강 확인 | 12장 · 7-2·7-3 · 22장 14-3 | 앞머리 YAML 파싱 |
| [llm-case-writer/SKILL.md](llm-case-writer/SKILL.md) | 정상 질문·회귀·변형 시험 문제 작성, 공격 유형은 자리표시 뼈대만 | 14·15·18·21·22장 · 9-1, 11-4, 13-4, 14-3 | 앞머리 YAML 파싱 |
| [llm-release-check/SKILL.md](llm-release-check/SKILL.md) | 키트 점검 → `serve_and_run.sh` 실행 → 출시 판단 요약(가능·조건부·불가 + 이유 3줄 + 역할별). 사람이 부를 때만 | 19·20장 · 12-2~12-4, 13-1 | 앞머리 YAML 파싱 |
| [llm-release-check/scripts/summarize.py](llm-release-check/scripts/summarize.py) | results.json 짧은 요약(표준 라이브러리, `python3 -I`) | 20장 | 랩 results.json 3개로 실행 |
| [settings/settings.example.json](settings/settings.example.json) | 권한(allow/ask/deny) + 훅 등록 예(exec 형식 `args`, `onFailure: block`) | 2장·19장 · 1-8, 12-2 | JSON 파싱 |
| [hooks/block-non-loopback.sh](hooks/block-non-loopback.sh) | PreToolUse(Bash): 공격 실습·평가 명령이 127.0.0.1 밖을 겨냥하면 차단(exit 2). 입력 해석 실패·예외도 차단(fail closed) | 2장 · 1-8 | `bash -n`, `test-hooks.sh` |
| [hooks/block-real-secrets.sh](hooks/block-real-secrets.sh) | PreToolUse(Write/Edit): FAKE 아닌 키·개인키 모양을 파일에 쓰면 차단. fail closed | 2장 · 1-8 | `bash -n`, `test-hooks.sh` |
| [hooks/test-hooks.sh](hooks/test-hooks.sh) | 훅 두 개에 깨진 입력·정상 입력 18가지 + 실행 권한 점검 | 2장 · 1-8 | 실행(아래) |

## 설치(내 프로젝트·랩 저장소 루트에서)

```bash
REPO=~/work/llm-security-in-practice   # git clone으로 받은 llm-security-in-practice 폴더(내 경로로 바꾼다)
mkdir -p .claude/skills .claude/hooks
cp -R "$REPO"/skills/llm-security-review "$REPO"/skills/llm-attack-tests \
      "$REPO"/skills/llm-case-writer "$REPO"/skills/llm-release-check .claude/skills/
cp "$REPO"/skills/hooks/*.sh .claude/hooks/ && chmod +x .claude/hooks/*.sh
cp "$REPO"/skills/settings/settings.example.json .claude/settings.json   # 이미 있으면 합친다
bash .claude/hooks/test-hooks.sh                                         # 훅이 fail closed인지 확인
```

- 스킬 부르기: `/llm-security-review samples/lab-app-py`, `/llm-attack-tests tests/attack`, `/llm-case-writer benign 환불`, `/llm-release-check full before,eval`. 앞의 셋은 "출시 전 보안 점검해 줘"처럼 말해도 설명을 보고 고른다. `llm-release-check`는 명령을 실행하므로 `disable-model-invocation: true`로 **사람이 부를 때만** 돈다.
- 랩(`samples/lab-app-py/`)을 저장소 루트로 쓸 때 설정의 상대 경로(`eval-kit/…`, `shopbot/…`, `attack-kit/…`)가 그대로 맞는다. venv를 켠 상태(`source .venv/bin/activate`)를 가정한다.
- 훅은 `python3`가 필요하다(JSON 읽기, `-I` 격리 모드).

## 앞머리에 쓴 필드 (skills 문서로 확인, 2026-10-28)

| 필드 | 쓴 스킬 | 뜻 |
| --- | --- | --- |
| `name` | 넷 다 | `/` 메뉴 이름. 폴더 이름과 같게 했다 |
| `description` | 넷 다 | 무엇을·언제. `when_to_use`와 합쳐 1,536자에서 잘린다 |
| `argument-hint` | 넷 다 | 자동 완성 힌트. 본문의 `$ARGUMENTS`가 인자 전체로 바뀐다 |
| `allowed-tools` | security-review·case-writer·release-check | 그 턴 동안 묻지 않고 쓸 도구를 **더할** 뿐, 다른 도구를 막지 않는다. Bash 규칙 안의 `${CLAUDE_SKILL_DIR}`는 스킬 폴더로 바뀐다 |
| `disallowed-tools` | security-review | 스킬이 도는 동안 `Edit`·`Write`·`NotebookEdit`를 뺀다(읽기 전용 점검) |
| `disable-model-invocation` | release-check | Claude가 스스로 부르지 않는다 |

- **Deny and ask rules still override `allowed-tools`**(skills 문서). 그래서 `llm-case-writer`가 `Edit`을 허용해도 `thresholds.yaml` 수정은 묻고, 비공개 입력 파일 읽기는 막힌다.
- `argument-hint`·`disallowed-tools`·`disable-model-invocation`은 Claude Code 전용 필드다. 같은 스킬을 claude.ai나 Skills API에 올리면 이 필드 때문에 오류가 난다(그쪽은 `name`·`description`·`license`·`compatibility`·`metadata`·`allowed-tools`만 허용). 이 강의는 Claude Code에서만 쓴다.

## 설정에서 지키는 것 (settings.example.json, 설계 5.8)

| 규칙 | 이유 |
| --- | --- |
| allow: `python -m pytest *`·`pytest *`, `uvicorn shopbot.main:app --host 127.0.0.1 *`, 가짜 LLM·가짜 MCP(`python -I tools/fake_*.py`), `mcp_tool_review.py`, `check-attack-ids.py`, `scan.sh`, `summarize.py`, `test-hooks.sh`, `evalkit validate/list/check-private`, `check.sh`, `serve_and_run.sh` | 테스트·랩 기동·읽기·점검 명령은 매번 묻지 않게 |
| ask: `flood.sh`·`run-attacks.sh`·`wobble.sh`·`docker compose` | 요청을 많이 보내거나 컨테이너를 띄우는 명령은 사람이 본다 |
| ask: `Edit(./.github/workflows/**)`, `thresholds.yaml`, `accepted_risks.yaml`, `eval-kit/ci/**`, `requirements.lock`, `shopbot/profiles/**` | 게이트 기준·수용한 위험·워크플로·잠금 파일·방어 스위치는 사람이 정한다(AI가 초록불을 만들지 않게, 19장) |
| deny: `.env`, 비공개 입력 파일 읽기·수정, `git push` | 비밀·공격 문구가 대화·로그로 새지 않게 |
| deny: `python -m evalkit *--allow-remote-target*`와 `python3` 형태 둘 다 | 내 PC 밖 대상 시험을 AI가 시작하지 않게 |
| deny: `uvicorn *0.0.0.0*`(`python -m uvicorn` 형태 포함) | 랩을 모든 네트워크에 여는 실행을 막는다(allow의 `--host 127.0.0.1 *` 뒤에 `--host 0.0.0.0`을 덧붙인 모양도 여기서 걸린다) |
| 훅: exec 형식 `"command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/<훅>.sh", "args": []` | hooks 문서 권장: 경로 자리표시를 쓰는 훅은 `args`를 둔다(셸 없이 그대로 한 인자). 스크립트에 실행 권한이 있어야 한다 |
| 훅: `"onFailure": "block"` | 훅이 시작 못 함·0/2 밖 종료 코드·시간 초과여도 그 동작을 막는다. **Claude Code v2.1.295 이상**(hooks 문서). 그보다 낮은 버전은 이 키를 모를 수 있지만, 훅 스크립트도 스스로 fail closed라 깨진 입력은 exit 2다 |

- **deny는 보안 경계가 아니다.** Bash deny는 Claude가 보통 만드는 형태만 잡는다. `sh -c '…'`·절대 경로 실행·스크립트 안 호출은 못 잡는다(permissions 문서). 실제 방어는 키트·스크립트 코드의 검사다(대상 호스트가 127.0.0.1이 아니면 `authorized_by` + `--allow-remote-target`가 둘 다 있어야 실행, `attack-kit/_loopback.sh`).
- 권한 규칙은 **공백 형식**(`Bash(python -m pytest *)`)을 쓴다. `:*`는 끝에 올 때만 같은 뜻으로 인정된다. 끝의 ` *`는 인자 없는 명령도 맞춘다.
- 복합 명령(`&&`·`;`·`|`)은 부분 명령마다 규칙을 본다. 작업 폴더 안으로의 `cd`는 읽기 전용으로 쳐서, `cd eval-kit && python -m evalkit validate cases`는 evalkit 규칙만 맞으면 묻지 않는다. deny·ask는 부분 명령 하나만 맞아도 걸린다.
- allow 규칙은 알려진 안전한 변수 외의 환경 변수 앞붙이기를 넘어서 일치하지 않는다. `LAB_PROFILES=before uvicorn …`·`LAB_DEFENSE_OFF=… uvicorn …`은 매번 묻는다(의도한 동작: 방어를 끄는 실행은 사람이 본다). deny·ask는 앞붙이기를 넘어서도 맞는다.
- 규칙은 deny → ask → allow 순서로 보고 처음 맞는 것이 이긴다.
- 경로: `./…`는 현재 폴더 기준, `/…`는 설정 출처 기준(프로젝트 설정이면 프로젝트 루트), `//…`는 절대 경로, `~/…`는 홈.
- `Read` deny는 Claude Code 파일 도구와 Claude가 알아보는 Bash 파일 명령(`cat`·`head`·`tail`·`sed` 등)에 적용된다. 파일 이름 없이 읽는 명령(`grep -r … .`)이나 파일을 스스로 여는 스크립트는 막지 못한다. 비공개 입력 파일은 **저장소 밖**에 두는 것이 가장 확실하다.
- `$schema` 주소 `https://json.schemastore.org/claude-code-settings.json`은 공식 settings 문서 예시와 같다. 편집기 자동 완성용이고 없어도 동작한다.
- 편집기가 `"onFailure"`에 스키마 경고를 띄울 수 있다. schemastore 스키마가 CLI보다 늦게 갱신되기 때문이라 무시해도 된다.
- 프로젝트 `.claude/settings.json`의 `permissions.allow`는 그 폴더를 신뢰(trust)한 뒤에야 적용된다. `deny`·`ask`는 바로 적용된다.
- Windows에서 Git Bash 없이 쓰면 Bash 도구가 등록되지 않아 `"matcher": "Bash"` 훅이 걸리지 않는다. 문서는 matcher를 `Bash|PowerShell`로 쓰라고 권한다. 이 강의는 Git Bash 또는 WSL을 가정하므로 예시는 `Bash`만 둔다.
- 실행 환경 자체를 격리하는 방법(컨테이너·프록시·샌드박스)은 이 강의 범위 밖이다.

## 실행 확인 결과(작성 환경, 2026-10-28, macOS · python3 3.14)

저장소 루트(`llm-security-in-practice`, 이 폴더의 한 칸 위)에서 `bash skills/hooks/test-hooks.sh`. 종료 코드 2 = 차단, 0 = 통과. 녹화용 기록은 `../samples/lab-app-py/_실측/1-8_hooks-fail-closed.txt`이고, `samples/lab-app-py/scripts/capture_all.sh`가 다시 만든다.

```text
block-non-loopback.sh        깨진 JSON                                  exit=2 blocked: hook error, fail closed (JSONDecodeError)
block-non-loopback.sh        빈 입력                                   exit=2 blocked: hook error, fail closed (JSONDecodeError)
block-non-loopback.sh        JSON 배열(모양 다름)                   exit=2 blocked: hook error, fail closed (TypeError)
block-non-loopback.sh        밖 주소(flood.sh)                         exit=2 차단: 공격 실습 명령은 http://127.0.0.1(내 PC의 랩)만 대상으로 합니다. 발견: http://203.0.113.5:8080
block-non-loopback.sh        @로 호스트 바꾸기                     exit=2 차단: 공격 실습 명령은 http://127.0.0.1(내 PC의 랩)만 대상으로 합니다. 발견: http://127.0.0.1:8080@203.0.113.5/api/chat
block-non-loopback.sh        localhost                                    exit=2 차단: 공격 실습 명령은 http://127.0.0.1(내 PC의 랩)만 대상으로 합니다. 발견: http://localhost:8080/api/chat
block-non-loopback.sh        127.0.0.1(통과)                            exit=0
block-real-secrets.sh        깨진 JSON                                  exit=2 blocked: hook error, fail closed (JSONDecodeError)
block-real-secrets.sh        FAKE 없는 키 모양                       exit=2 차단: 파일에 API 키 모양이(가) 들어갑니다. 랩에서는 FAKE가 들어간 가짜 값만 씁니다(예: sk-test-FAKE-0000).
block-real-secrets.sh        FAKE 키(통과)                             exit=0
block-non-loopback.sh        python3 없음(PATH에 cat만)               exit=2 hooks/block-non-loopback.sh: line 18: python3: command not found blocked: hook error, fail closed (exit 127)
block-non-loopback.sh        실행 권한(exec 형식)                   ok
```

(`_실측/1-8_hooks-fail-closed.txt`의 전체 18줄 + 실행 권한 2줄 중 12줄을 그대로 옮김.) 훅을 직접 실행(exec 형식과 같음)해 랩 명령도 확인했다: `uvicorn shopbot.main:app --host 127.0.0.1 --port 8080`·`python -m pytest -q`·`bash eval-kit/scripts/serve_and_run.sh full before,eval`은 exit 0, `curl … http://localhost:8080/api/chat`은 exit 2.

키 모양 입력은 `K="sk-$(printf 'x%.0s' $(seq 24))"`처럼 즉석에서 만든다(파일에는 남기지 않는다).

## 확인 필요

- 훅 `"onFailure": "block"`은 v2.1.295 이상에서만 동작한다. 쓰는 Claude Code 버전을 `claude --version`으로 확인한다.
- 훅 입력 JSON 필드 이름(`tool_input.command`·`content`·`new_string`)은 hooks 문서 기준이다. 버전이 바뀌면 다시 확인한다.
- 훅은 방어의 보조다. 실습 스크립트 자체(`_loopback.sh`, evalkit의 대상 검사, `mcp_tool_review.py`의 `require_loopback`)가 127.0.0.1 밖을 거부하는 것이 1차 방어다.
