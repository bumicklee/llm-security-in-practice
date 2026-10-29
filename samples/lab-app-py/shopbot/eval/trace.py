"""eval 프로필의 도구 호출 기록. 기록 자체는 TraceRecorderMiddleware가 요청 컨텍스트(LabContext.trace)에 모은다.

응답 모양: {"intent", "orderId", "answer", "trace": {"request_id": "req-…", "tool_calls": [{name, arguments, status}]}}
status: EXECUTED(실행됨) · PROPOSED(승인 대기에 넣음) · DENIED(앱이 막음). 도구 결과 본문은 넣지 않는다.
평가 키트의 금지 도구 판정은 EXECUTED만 실패로 센다(대상 설정 tool_not_called_fails_on: executed).
기본 프로필 응답 모양({intent, orderId, answer})은 바뀌지 않는다(web/chat.py가 eval일 때만 trace를 붙인다).
"""
STATUSES = ("EXECUTED", "PROPOSED", "DENIED")
