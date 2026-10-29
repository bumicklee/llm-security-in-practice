# 프롬프트: 출력 스키마(구조화 출력 + response_model)와 거절 문구 적용

- **쓰는 곳:** 4장 4.4, 수업 2-6
- **도구:** Claude Code
- **목적:** 상담봇 답을 `{intent, orderId, answer}` 모양으로 고정하고, 벗어나면 정해진 문구로 바꾸게 한다.

## 프롬프트 본문

```text
{채팅_파일} 의 채팅 응답을 출력 스키마로 바꿔라.

1. Pydantic 모델 {답_타입}(intent: Intent | None, orderId: str | None, answer: str | None) 와
   str Enum Intent { {의도_목록} } 를 만든다. 필드 이름은 기존 API 계약(camelCase)을 지킨다.
2. 모델 호출을 구조화 출력으로 바꾼다.
   - create_agent 를 쓰면 response_format=ProviderStrategy({답_타입}) (모델에 json_schema 를 함께 보낸다)
   - 모델을 직접 부르면 model.with_structured_output({답_타입}, method="json_schema")
   변환 실패(예외)·structured_response 없음은 잡아서 거절 답으로 바꾼다. 방어가 막은 예외(입력 거부·한도 초과)는 그대로 올린다.
3. 순수 Python {정책_클래스}.enforce(reply):
   - intent·answer None → 거절
   - orderId 가 있으면 숫자 4~10자리만
   - answer {최대_글자}자 초과 → 거절
   - answer 에 비밀 모양({비밀_패턴}) → 거절
   거절 답은 (UNKNOWN, None, "{거절_문구}")
4. 엔드포인트에 response_model={답_타입} 을 붙여 나가는 JSON 모양도 고정한다.
5. pytest: 규칙마다 한 개씩, 그리고 정상 답은 그대로 통과. 가짜 채팅 모델로 키·네트워크 없이.
6. 바뀐 부분만 diff로.
LangChain API 이름이 확실하지 않으면 # 확인 필요 주석을 단다.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{채팅_파일}` | `shopbot/web/chat.py` |
| `{답_타입}` | `BotReply` |
| `{의도_목록}` | `ORDER_STATUS, CANCEL_REQUEST, PRODUCT_QA, UNKNOWN` |
| `{정책_클래스}` | `ReplyPolicy` |
| `{최대_글자}` | 300 |
| `{비밀_패턴}` | `FAKE-VIP-\d{4}`, `sk-test-FAKE[\w-]*`, `CANARY-[A-Z0-9]{6,}` |
| `{거절_문구}` | 도와드릴 수 없는 요청입니다 |

## 기대 출력 예

```json
{"intent":"UNKNOWN","orderId":null,"answer":"도와드릴 수 없는 요청입니다"}
```

랩 정답: `samples/lab-app-py/shopbot/agent/schemas.py`(`BotReply`), `shopbot/agent/factory.py`(`ProviderStrategy(BotReply)`, 스위치 `output_schema`), `shopbot/web/chat.py`(`run_chat`, `response_model`), `labcore/injection/__init__.py`(`ReplyPolicy`, `LeakDetector`, `REFUSAL`). 지키는 테스트: `tests/unit/test_injection.py::test_스키마를_벗어난_답은_정해진_문구로`.

## 주의

- 스키마는 "말할 수 있는 범위"를 줄일 뿐이다. `answer` 칸 안에는 여전히 아무 글이나 들어갈 수 있으므로 3번 검사가 필요하다.
- 모델·서버가 `json_schema` 구조화 출력을 지원하는지 확인한다. 로컬 모델(LM Studio)은 작은 모델에서 형식을 잘 못 지킬 수 있다(【작성자 실측】).
- 비밀 패턴에 진짜 키 형식을 넣지 않는다. 랩은 가짜 형식만.
