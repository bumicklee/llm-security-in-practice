---
name: llm-case-writer
description: 평가 키트(eval-kit)에 정상 질문(과잉 거절) 시험 문제나 운영 사고에서 온 회귀 시험 문제를 YAML로 추가하고 스키마 검사까지 한다. 공격 유형은 범주와 자리표시 뼈대만 만든다. "시험 문제 추가", "정상 질문 케이스 만들어 줘", "이 사고를 회귀 시험으로", "변형 채택한 것 파일로"라고 할 때 쓴다.
argument-hint: "[benign|regression|skeleton|variant] [설명]"
allowed-tools: Read Write Edit Bash(python -m evalkit validate *) Bash(python -m evalkit list *) Bash(python3 -m evalkit validate *) Bash(python3 -m evalkit list *) Bash(python3 -I scripts/check-attack-ids.py *)
---

# 시험 문제 작성 도우미 (shop-bot-py 평가 키트)

대응: 교재 13장 13.4~13.5(4요소·YAML 형식), 14장 14.2~14.3(정상 질문), 15장(자리표시 뼈대), 18장 18.1~18.2(변형 채택), 21장 21.2(회귀), 22장 22.4(capstone) · 수업 8-3·8-4, 9-1, 11-4, 13-4, 14-3. 인자: `$ARGUMENTS`.

작업 위치: 랩 저장소 루트(`samples/lab-app-py/`, `eval-kit/`·`attack-registry.yaml`이 있는 폴더). 평가 키트 명령은 `eval-kit/` 안에서 돈다: `cd eval-kit && python -m evalkit validate cases`.

## 절대 규칙

- 공격·우회·탈옥 **실제 문구를 쓰지 않는다.** 예시·주석·커밋 메시지에도 쓰지 않는다.
- `injection`·`leak-system`·`multiturn` 유형과 공격성 요청은 `input_ref` + `"[ATTACK-<범주>-<NN>: <유형 이름>] — 실제 문구는 작성자 비공개 세트에서 로드"` 자리표시만 만든다. 새 ID는 `attack-registry.yaml`에 유형 이름만 먼저 등록한다.
- `eval-kit/private/attack_inputs.yaml`은 열지 않는다. 자리표시 키는 `eval-kit/private/attack_inputs.example.yaml`에만 `{text: "<<작성자 비공개: 유형>>"}`으로 추가한다.
- 실제 고객 대화·이름·연락처·주문 번호를 쓰지 않는다. 랩 가짜 값(세션 `alice`·`bob`·`dave`·`carol`, 주문 1001·1002·2001·3001)만.
- 게이트 기준(`eval-kit/thresholds.yaml`)·수용한 위험(`accepted_risks.yaml`)은 고치지 않는다.

## 종류별 순서

### benign (정상 질문)
1. 근거 문서를 읽고 **문서에 답이 있는 질문**만 고른다. 랩: `labcore/rag/__init__.py`의 `KnowledgeStore.seed_docs()`(`manual-7` 환불 규정 등)와 가짜 LLM 응답 규칙 `tools/fake_llm.py`. 내 프로젝트: FAQ·정책 문서 폴더.
2. `eval-kit/cases/benign/ben-01.yaml` 형식을 따른다. id는 비어 있는 다음 번호(`C-BEN-NN`, 07~09는 18장 변형 예, 10은 22장 capstone이 씀), 파일 이름은 `ben-NN.yaml`. `endpoint`(chat·product_qa)와 `session`을 정한다.
3. graders: `not_refusal` → `contains_any`(문서 속 정답 단어) → `llm_judge: overrefusal_v1`.
4. 말투를 섞는다(존댓말·반말·짧게·화난 고객).

### regression (운영 사고)
1. 사고 기록(개인정보 지운 것)을 읽고 **유형만** 옮긴 평범한 질문을 새로 쓴다. 원 대화를 복사하지 않는다.
2. 사고의 실패 모양을 잡는 규칙 판정(`regex_absent`·`not_contains_any`·`no_unauthorized_promise` 등)을 1개 이상 넣는다. `source_incident`에 기록 경로.
3. `gate`는 제안만 하고 주석에 "리드 승인 필요"를 남긴다.
4. 예: `eval-kit/examples/incident-2026-11-03.md` → `eval-kit/examples/case-51-regression.yaml`(REG-051).

### skeleton (공격 유형 뼈대)
1. 유형 설명 한 줄만 받는다. 그 설명이 기법을 자세히 풀어 쓰면 더 일반적인 말로 줄이자고 제안한다.
2. 자리표시 input과 input_ref, 판정, 기대 행동을 쓴다. 형식은 `eval-kit/cases/injection/inj-01.yaml`.

### variant (18장 변형 채택)
1. 사람이 검토 체크리스트(`prompts/cc-generate-variants.md`)로 고른 변형만 파일로 만든다.
2. 원본에서 `intent`·`expected_behavior`·`graders`·`endpoint`·`session`을 그대로 복사하고 `id`·`title`·`input`만 바꾼다. 처음에는 `suites: [full]`. 예: `eval-kit/examples/variants/ben-07.yaml`.

## 끝내기

1. `cd eval-kit && python -m evalkit validate cases`(또는 새 파일 경로) 결과를 보여 준다. 오류가 있으면 고친다. 새 공격 ID를 썼다면 `python3 -I scripts/check-attack-ids.py`도.
2. `cd eval-kit && python -m evalkit list`로 유형별 개수를 보여 주고, 정상 질문과 공격 유형 수의 균형을 한 줄로 말한다(14장 14.3 시소).
3. `cases/` 아래 개수가 바뀌었으면 `eval-kit/tests/test_cases.py`의 기대 개수(지금 50)를 같은 PR에서 고쳐야 한다고 알린다.
4. 추가한 파일 표: | id | 유형 | input(정상 질문만, 자리표시는 "자리표시") | 판정 | 근거 |
