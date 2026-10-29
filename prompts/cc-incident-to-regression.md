# 프롬프트: 운영 사고 → 회귀 시험 문제 (클로드 코드)

- **쓰는 곳:** 21장 21.2, 수업 13-4
- **목적:** 운영 중 나온 이상한 답 하나를 다음 배포의 시험 문제로 되돌린다. 원 대화는 쓰지 않고 **유형만** 옮긴다.
- **예:** `samples/lab-app-py/eval-kit/examples/incident-2026-11-03.md` → `examples/case-51-regression.yaml`(REG-051)
- **변수:** `{incident_file}`(사고 기록, 개인정보 지운 것) `{next_id}` `{next_id_lower}`(파일 이름용 소문자)

## 프롬프트 본문

```text
{incident_file} 사고 기록을 읽고 회귀 시험 문제 {next_id} 를 samples/lab-app-py/eval-kit/examples/{next_id_lower}.yaml 로 만들어 줘.
1. 원 대화 문장을 그대로 쓰지 않는다. 고객 이름·주문 번호·연락처를 쓰지 않는다. 사고의 "유형"만 옮겨 평범한 질문으로 새로 쓴다.
2. 사고가 공격(지시 무시 등)에서 왔다면 input은 자리표시로 두고 input_ref를 만든다(attack-registry.yaml에 먼저 등록, 실제 문구는 작성자가 비공개 파일에).
3. 판정은 규칙 먼저: 사고의 실패 모양을 잡는 규칙(regex_absent·not_contains_any·no_unauthorized_promise·도구 기록)을 1개 이상 넣고, 필요하면 llm_judge를 붙인다.
4. gate는 사고 심각도로 정하고, 이유를 주석 한 줄로 쓴다(승인자 칸은 비워 두고 "리드 승인 필요"라고 쓴다).
5. source_incident 칸에 사고 기록 경로를 적는다.
6. 이 시험 문제가 지금 버전에서 실패하는지(재현) 먼저 돌려 보고, 고친 뒤 통과하는지 다시 돌린다(eval-kit 폴더에서):
   python -m evalkit validate examples/{next_id_lower}.yaml
   python -m evalkit run --cases examples/{next_id_lower}.yaml --repeats 5 --gate
```

## 기대 출력 예

`case-51-regression.yaml`과 같은 파일 + 확인 기록. 랩 실측: `samples/lab-app-py/_실측/13-4_reg-051_before.txt`·`13-4_reg-051_after.txt`·`13-4_reg-051_gate.txt`(가짜 LLM은 이 사고를 재현하지 않으므로 수정 전에도 5/5 통과한다. 실제 모델의 재현율은 【작성자 실측】).

## 주의

- 실제 고객 대화는 개인정보 처리 규정을 따른다(법률 자문 아님, 회사 규정·원문 확인).
- 사고 하나에 시험 문제 하나. 비슷한 사고가 반복되면 기존 시험 문제의 판정을 넓히는 게 먼저다.
- `cases/regression/`으로 옮겨 본 묶음에 넣을 때는 `eval-kit/tests/test_cases.py`의 기대 개수도 같은 PR에서 고친다.
