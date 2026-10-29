---
name: llm-release-check
description: LLM 기능의 출시 전 점검 키트(eval-kit)를 키트 점검 → 실행 → 요약 순서로 돌리고 결과를 출시 판단 요약(가능·조건부·불가 + 이유 3줄 + 개발·QA·리드별)으로 정리한다. "출시 점검", "릴리스 체크", "게이트 돌려 줘", "LLM 시험 돌려 줘"라고 할 때 쓴다. 내 PC의 랩 앱 shop-bot-py(127.0.0.1)만 대상으로 한다.
argument-hint: "[quick|full] [eval|before,eval]"
disable-model-invocation: true
allowed-tools: Read Bash(bash eval-kit/scripts/check.sh) Bash(bash eval-kit/scripts/serve_and_run.sh *) Bash(python -m evalkit report *) Bash(python -m evalkit check-private *) Bash(python3 -I ${CLAUDE_SKILL_DIR}/scripts/summarize.py *)
---

# LLM 출시 전 점검 실행과 요약

대응: 교재 19장(게이트), 20장 20.1~20.4(보고서·요약) · 수업 12-2~12-4, 13-1. 작업 위치는 랩 저장소 루트(`samples/lab-app-py/`, `eval-kit/`·`shopbot/`·`.venv/`가 있는 폴더)다.

인자: `$ARGUMENTS` — 첫 값은 묶음(`quick` 기본 21개, `full` 50개), 둘째 값은 shop-bot-py 프로필(`eval` 기본 = 수정 후, `before,eval` = 수정 전). 프로필에는 반드시 `eval`이 들어가야 한다(reset·fixtures·trace).

## 지켜야 할 것 (먼저 읽기)

1. 대상은 `127.0.0.1`의 내 앱뿐이다. `eval-kit/targets/*.yaml`의 `base_url`·`health_url`이 다른 주소면 멈추고 사용자에게 알린다. `--allow-remote-target`을 스스로 붙이지 않는다.
2. `eval-kit/private/attack_inputs.yaml`은 **읽지도, 출력하지도, 고치지도 않는다.** 채운 개수는 `cd eval-kit && python -m evalkit check-private`로만 본다.
3. 게이트를 초록으로 만들려고 `thresholds.yaml`, `accepted_risks.yaml`, 시험 문제의 `graders`, 방어 스위치(`shopbot/profiles/*.yaml`)를 고치지 않는다. 그런 변경이 필요해 보이면 제안만 하고 사람 결정을 기다린다.
4. 요약에는 보고서에 있는 숫자만 쓴다. 원인은 "추정"이라고 표시한다. 공격 입력 문구를 인용하지 않는다.

## 순서

1. 키트 자체 점검(모델·앱 없이, 문법·키트 단위 테스트·스키마·공격 ID 등록부):
   ```bash
   bash eval-kit/scripts/check.sh
   ```
   실패하면 여기서 멈추고 어느 단계(`[1/5]`~`[5/5]`)가 실패했는지 보고한다. `samples/extras/support-bot-python/`이 없으면(랩만 따로 복사한 경우) `[1/5]`가 "support-bot-python 없음 → … 건너뜀"을 찍고 상담봇 문법 검사와 끝에서 끝까지 테스트 4개를 건너뛴다. 실패가 아니다(19장).
2. 실행(가짜 LLM·uvicorn이 안 떠 있으면 스크립트가 잠깐 띄웠다 내린다):
   ```bash
   bash eval-kit/scripts/serve_and_run.sh <묶음> <프로필>
   ```
   환경 변수 앞붙이기(`SUITE=… bash …`)는 쓰지 않는다. Claude Code의 allow 규칙은 알려진 안전한 변수 외의 앞붙이기를 넘어서 일치하지 않아 매번 묻는다(permissions 문서). 위치 인자로 넘긴다.
   종료 코드: 0 = 초록·노랑, 1 = 빨강, 2 = 설정 오류, 3 = 연결 실패. 1은 "점검이 제 일을 한 것"이지 스킬 실패가 아니다.
   "이미 떠 있는 shop-bot-py를 씁니다" 줄이 나오면, 그 앱이 요청한 프로필로 띄운 것인지 사용자에게 확인한다.
3. 결과 요약 뽑기(큰 results.json을 통째로 읽지 않는다):
   ```bash
   python3 -I ${CLAUDE_SKILL_DIR}/scripts/summarize.py eval-kit/results/latest/results.json
   ```
   지난 기준이 있으면 `--baseline <기준 results.json>`을 붙인다(예: main의 full 산출물).
4. `eval-kit/results/latest/report.md`를 읽고 아래 형식으로 답한다. 리드용 3줄은 `prompts/report-summary-lead.md`, 역할별은 `prompts/report-summary-audience.md`와 같은 규칙이다.

## 답 형식

```text
판단: <출시 가능 | 조건부 출시 | 출시 불가>  (게이트 <GREEN|YELLOW|RED>, <묶음>, 프로필 <프로필>, 채점관 <모드>)
1. <막는 실패: 유형별 개수와 id>
2. <경고·보류·수용한 위험>
3. <지난 실행 대비 변화 또는 "비교 기준 없음">

개발자에게: <고칠 것 우선순위 1~3개, 판정 이유 붙여서>
QA에게: <믿기 어려운 판정(보류·채점관 off·heuristic·한도 도달·가짜 LLM 결과), 반복 횟수를 늘릴 시험 문제>
리드에게: <정해야 할 것, 또는 "결정 필요 없음">
보고서: eval-kit/results/latest/report.html
```

랩 기대값: `full before,eval` → RED 43/50, `full eval` → GREEN, `quick before,eval` → RED(`_실측/9-8_full_before.txt`·`9-8_full_after.txt`·`12-3_quick_before.txt`).

## 자주 막히는 곳

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| 종료 코드 3 | 8080·8082 포트에 다른 프로그램, 또는 앱 시작 실패(트레이싱 변수가 켜져 있으면 시작 거부) | `eval-kit/.shop-bot.log`·`eval-kit/.fake-llm.log` 확인, 포트 정리 후 다시 |
| 결과가 기대와 반대(수정 전인데 GREEN) | 예전에 띄운 앱이 그대로 떠 있음 | 스크립트 첫 줄의 "이미 떠 있는" 안내를 확인, 그 앱을 내리고 다시 |
| `PROFILE에 eval이 없습니다` | 둘째 인자에 `eval` 빠짐 | `eval` 또는 `before,eval` |
| 채점관 칸이 전부 skip | `JUDGE=off`(기본) | 실제 판정은 `JUDGE=openai`(로컬 모델 필요, 사람이 직접 실행). `heuristic`은 데모용이라 출시 판단에 쓰지 않는다 |
