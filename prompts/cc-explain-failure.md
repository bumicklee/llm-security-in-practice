# 프롬프트: 빨간불 읽기 — 실패 원인 좁히기 (클로드 코드)

- **쓰는 곳:** 19장 19.7, 수업 12-4 · 20장 20.2
- **목적:** PR에서 게이트가 빨간불일 때, 보고서와 바뀐 파일을 같이 보고 "어느 변경이 어느 실패를 만들었나"를 좁힌다.
- **변수:** `{report_md}` `{diff}`(PR 변경 내용, 예: `git diff origin/main...HEAD -- shopbot/profiles labcore/injection`)

## 프롬프트 본문

```text
LLM 출시 게이트가 빨간불이다. 아래 보고서와 변경 내용을 보고 원인을 좁혀 줘. 코드는 아직 고치지 마.
[보고서]
{report_md}
[변경]
{diff}
1. 실패한 시험 문제를 유형별로 묶는다.
2. 변경된 줄 중 그 유형과 관련 있어 보이는 줄을 짝지어 표로 보여 준다(관련 근거 한 줄).
   방어 스위치(shopbot/profiles/*.yaml 의 defense.*), 시스템 프롬프트 상수, 미들웨어 목록, 의존성 순서를 먼저 본다.
3. "지난 실행 대비 새 실패"만 이번 변경의 영향으로 본다. 원래 실패하던 것은 따로 적는다.
4. 확인 실험을 제안한다: 의심 줄만 되돌리거나, 스위치 하나만 바꿔(LAB_DEFENSE_OFF=…) 같은 묶음을 돌리는 명령.
5. 게이트를 끄거나 기준선을 낮추거나 시험 문제를 지우는 해결책은 제안하지 않는다.
```

## 입력 예 / 기대 출력 예

변경: `shopbot/profiles/default.yaml`에서 `secret_free_prompt: true → false`, `output_schema: true → false`(두 줄)

```text
| 실패 | 관련 변경 | 근거 |
| C-INJ-01·02, C-START-02 (새 실패) | default.yaml secret_free_prompt: false | 수정 전 시스템 프롬프트(SystemPrompts.BEFORE)로 돌아가 비밀이 프롬프트에 들어감 |
| C-LEAK-01·04, C-START-03, C-MT-01 (새 실패) | default.yaml output_schema: false | 구조화 출력·ReplyPolicy를 지나지 않아 카나리·비밀 검사가 빠짐 |
확인 실험: LAB_PROFILES=eval LAB_DEFENSE_OFF=secret_free_prompt uvicorn shopbot.main:app --host 127.0.0.1 --port 8080
          (cd eval-kit && python -m evalkit run --suite quick --gate)
```

실측: 두 스위치를 함께 끈 PR은 quick 21개 중 7개 실패·RED(`samples/lab-app-py/_실측/12-4_output-check-off.txt`), 프롬프트 스위치 하나만 끈 PR은 GREEN(`12-4_switch-one-off.txt`, 출력 검사가 남아 막음). 같은 설정 PR을 pytest 잡에 넣으면 앱 테스트 1개가 잡는다(`12-4_pytest-config-pr.txt`).

## 주의

- "스위치 하나만 끈 PR이 초록"은 방어가 여러 겹이라는 뜻이지 그 변경이 안전하다는 뜻이 아니다. 리뷰에서 방어를 끄는 변경으로 따로 표시한다(`review-llm-feature-pr.md`).
