# private/ — 공격 유형 실제 문구를 두는 자리(비공개)

- 이 폴더의 `attack_inputs.yaml`은 `.gitignore` 대상이다. **커밋하지 않는다.**
- 공개 저장소에는 형식 예시 `attack_inputs.example.yaml`만 있다. 모든 값이 `<<작성자 비공개: 유형>>` 자리표시다.
- 시험 문제 파일(`cases/**.yaml`)은 `input_ref: ATTACK-INJ-01`로 이 파일의 항목을 가리킨다. 항목이 없거나 비어 있으면 공개 자리표시 문장 그대로 보낸다.
- 가짜 LLM(tools/fake_llm.py)은 자리표시 표식 `[ATTACK-<범주>-<번호>: 유형 이름]`을 알아보고 약한 모델을 흉내 낸다. 그래서 비공개 파일 없이도 수업의 모든 화면(빨간불·보고서)이 재현된다.
- 이 폴더는 선택 기능이다. 자리표시로 잰 실제 모델 숫자는 장치 확인용일 뿐이라, 실제 공격 통과율을 재려면 검토한 문구를 여기에 채운다. 작성자는 비공개 세트 대신 공개 도구(garak·promptfoo)로 쟀다(18장, `_실측/11-5_promptfoo-gptoss.txt`·`11-6_garak-gptoss.txt`).
- 확인: `python3 -m evalkit check-private` (채운 개수만 출력, 문구는 출력하지 않음)
