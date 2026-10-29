# 프롬프트: 다른 앱에 붙이기 — 대상 설정 만들기 (클로드 코드)

- **쓰는 곳:** 13장 13.1, 수업 8-1 · 21장 21.4, 수업 13-6 · 부록 H
- **목적:** 채점기는 HTTP만 부른다. 다른 스택(FastAPI 다른 앱·Node·Go 등)의 내 앱을 시험하려면 `targets/<이름>.yaml` 하나만 만든다.
- **예:** `samples/lab-app-py/eval-kit/targets/shop-bot-py.yaml`(기본, FastAPI 랩), `support-bot-python.yaml`(빌드 없는 Python 상담봇)
- **변수:** `{app_path}` `{target_name}`

## 프롬프트 본문

```text
{app_path} 앱의 채팅 API를 찾아서 samples/lab-app-py/eval-kit/targets/{target_name}.yaml 을 만들어 줘. targets/shop-bot-py.yaml 형식을 따른다.
1. base_url·health_url 은 반드시 http://127.0.0.1:<포트>. 다른 주소는 쓰지 않는다.
2. chat.path / method / body(필드 이름에 {session} {input} "{history}" 끼우기) / reply_field / tool_calls_field 를 코드에서 찾아 채운다.
   FastAPI 앱이면 @app.post·@router.post 와 요청·응답 Pydantic 모델에서 찾는다. 못 찾으면 "확인 필요" 주석.
3. 로그인이 필요하면 sessions(가짜 계정)와 default_session 을 만든다. 실제 계정·토큰을 쓰지 않는다.
4. 도구 호출 기록을 응답에 넣는 시험 전용 스위치(예: eval 프로필의 trace.tool_calls)가 있는지 찾는다. 없으면 tool_calls_field를 비우고, 도구 시험(tool·authz)은 이 대상에서 돌릴 수 없다고 적는다.
5. 시험용 문서 넣기(admin.fixtures_path)·상태 되돌리기(reset)가 없으면 indirect·multiturn 시험은 빼고 돌리라고 적는다.
6. canaries·pii_registry·order_owners·tenant_docs 는 그 앱의 시험 데이터(가짜)로 채운다. 실제 고객 값을 쓰지 않는다.
7. 마지막에 연결만 확인한다(앱이 떠 있을 때, eval-kit 폴더에서):
   cd samples/lab-app-py/eval-kit && python -m evalkit run --target targets/{target_name}.yaml --cases cases/portable --repeats 1
```

## 입력 예

`{app_path}` = `samples/extras/support-bot-python`, `{target_name}` = `support-bot-python-copy`

## 기대 출력 예

`support-bot-python.yaml`처럼 경로·필드가 채워진 설정 + "tool_calls_field: 없음 — 도구 시험은 이 대상에서 빠진다" 같은 메모. 연결 확인 출력은 `samples/lab-app-py/_실측/13-6_portable_support-bot-v4.txt` 모양(시험 문제 5개, 게이트 색 한 줄).

## 주의

- 회사 시험 서버를 대상으로 할 때는 담당자 허락을 먼저 받고, 대상 설정에 `authorized_by`를 적은 뒤 `--allow-remote-target`으로만 실행한다. 클로드 코드 설정 예시(`../skills/settings/settings.example.json`)는 이 플래그를 deny에 둔다(사람이 직접 실행).
- portable 시험 문제(`cases/portable/`)는 대상 설정 값만으로 판정한다. 다른 스택에서는 이 5개부터 돌린다.
