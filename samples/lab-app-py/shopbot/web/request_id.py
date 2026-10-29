"""요청마다 요청 ID를 만들고 응답 헤더 X-Request-Id로 돌려준다(11장 11.4).

순수 ASGI 미들웨어라서 401·429·400 응답에도 붙는다. 값은 contextvars(RequestIds)로 감사 로그·도구 기록까지 이어진다.
"""
from labcore.audit import RequestIds


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = RequestIds.begin()
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            RequestIds.end()
