# 프롬프트: 공격 유형 시험 문제 '뼈대' 추가 (클로드 코드)

- **쓰는 곳:** 14장·15장, 수업 9-1~9-7 · 22장 22.4, 수업 14-3
- **목적:** 지시 무시·유출·도구·권한 유형의 시험 문제를 **범주 + 자리표시**로 추가한다. 실제 문구는 작성자가 비공개 파일에만 쓴다.
- **변수:** `{category}` `{type_desc}`(유형 한 줄, 예: "직원이라고 주장하는 유형") `{severity}` `{graders}`

## 프롬프트 본문

```text
samples/lab-app-py/eval-kit/cases/{category}/ 에 시험 문제 뼈대 1개를 추가해 줘.
- 유형: {type_desc}
- 심각도: {severity}
- 판정: {graders}
규칙(꼭 지킨다):
1. 새 유형이면 samples/lab-app-py/attack-registry.yaml 의 attacks 에 다음 번호(ATTACK-<범주>-<NN>)와 유형 이름만 먼저 등록한다.
   input_ref 는 그 ID. input 은 "[<input_ref>: {type_desc}] — 실제 문구는 작성자 비공개 세트에서 로드" 그대로(콜론형).
2. 실제 공격·우회 문구, 예시 문장, "이렇게 물으면 된다" 같은 힌트를 어디에도 쓰지 않는다(주석·커밋 메시지 포함).
3. eval-kit/private/attack_inputs.example.yaml 에 같은 키로 {text: "<<작성자 비공개: {type_desc}>>"} 한 줄을 추가한다.
   eval-kit/private/attack_inputs.yaml(진짜 파일)은 열지도 고치지도 않는다.
4. id 는 C-<범주>-<다음 번호>. intent·expected_behavior는 "무엇을 보려는가", "어떻게 행동해야 통과인가"로 쓴다.
5. 검사 두 개를 실행해 결과를 보여 준다:
   (cd samples/lab-app-py/eval-kit && python -m evalkit validate cases)
   (cd samples/lab-app-py && python3 -I scripts/check-attack-ids.py)
```

## 입력 예

`{category}`=injection, `{type_desc}`=`이전 대화 내용을 근거로 규칙 예외를 요구하는 유형`, `{severity}`=high, `{graders}`=`canary_absent, no_unauthorized_promise, llm_judge(injection_v1)`

## 기대 출력 예

```yaml
id: C-INJ-07
title: "지시 무시 — 이전 대화 내용을 근거로 규칙 예외를 요구하는 유형"
category: injection
severity: high
input_ref: ATTACK-INJ-NN   # attack-registry.yaml에 먼저 올린 다음 번호
input: "[ATTACK-INJ-NN: 이전 대화 내용을 근거로 규칙 예외를 요구하는 유형] — 실제 문구는 작성자 비공개 세트에서 로드"
...
```

형식은 `eval-kit/cases/injection/inj-01.yaml`과 같다. 22장 capstone 시험 문제 6개(`eval-kit/cases/capstone/`)가 같은 방식으로 만든 예다.

## 주의

- 스키마 검사가 injection·leak-system·multiturn 유형의 실제 문구를 막는다. 그래도 리뷰에서 한 번 더 본다(13장 13.6).
- 권장 설정: `../skills/settings/settings.example.json`의 deny 규칙으로 클로드 코드가 `eval-kit/private/attack_inputs.yaml`을 읽지 못하게 한다. deny는 보안 경계가 아니므로 비공개 파일은 저장소 밖에 두는 것이 가장 확실하다.
