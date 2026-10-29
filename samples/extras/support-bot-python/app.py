"""가나다몰 상담 챗봇 (실습 앱) — 표준 라이브러리만 쓰는 작은 HTTP 서버.

목적: 출시 전 점검의 '시험 대상'. 채점기는 이 앱을 HTTP로만 부른다.
대응 장: 21장 21.4(다른 스택에 붙이기, 수업 13-6). 이 앱은 키트를 다른 스택에 붙여 보는 예다
실행:
    cd samples/extras/support-bot-python
    cp .env.example .env          # 처음 한 번
    python3 app.py                # http://127.0.0.1:8000
    BOT_PROFILE=v4 python3 app.py # 고친 버전으로 띄우기
API:
    GET  /health                  → 상태·모드·프롬프트 버전
    POST /chat                    → {"session": "sess-A-FAKE", "message": "...", "history": [...]}
                                     응답 {"reply", "request_id", "trace"(EXPOSE_TRACE=1일 때만)}
    POST /admin/fixtures          → {"enabled": true|false} 시험용 문서 넣기/빼기 (ADMIN_ENDPOINTS=1, 127.0.0.1만)
    POST /admin/reset             → 주문 상태·도구 기록 초기화
    GET  /admin/tool-log          → 최근 도구 호출 기록
주의: 시험 환경 전용 기능(trace, /admin/*)은 운영에서 끈다(EXPOSE_TRACE=0, ADMIN_ENDPOINTS=0).
FastAPI가 아니라 http.server를 쓴 이유: 외부 패키지 설치 없이 바로 돌리기 위해서다.
"""
import json
import sys
import urllib.error
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bot import make_bot
from config import Settings
from retrieval import Retriever
from store import Store

MAX_BODY = 32 * 1024

PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>가나다몰 상담 챗봇 (실습용)</title>
<style>body{font-family:sans-serif;max-width:640px;margin:2rem auto}#log div{margin:.4rem 0}
.u{color:#1d4ed8}.b{color:#065f46}.t{color:#9a3412;font-size:.85rem}</style></head><body>
<h1>가나다몰 상담 챗봇 <small>(가짜 데이터 · 127.0.0.1 전용)</small></h1>
<p>세션: <select id="s"><option>sess-A-FAKE</option><option>sess-B-FAKE</option><option>sess-C-FAKE</option></select>
<span id="h"></span></p>
<div id="log"></div>
<form id="f"><input id="m" size="50" placeholder="예: 환불은 며칠 안에 신청해야 하나요?"><button>보내기</button></form>
<script>
fetch('/health').then(r=>r.json()).then(j=>{document.getElementById('h').textContent=
 ' 모드 '+j.mode+' · 프롬프트 '+j.prompt_version});
const log=document.getElementById('log');
function add(c,t){const d=document.createElement('div');d.className=c;d.textContent=t;log.appendChild(d);}
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const m=document.getElementById('m');
 add('u','나: '+m.value);
 const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({session:document.getElementById('s').value,message:m.value})});
 const j=await r.json();add('b','챗봇: '+(j.reply||j.error));
 if(j.trace&&j.trace.tool_calls.length)add('t','도구 기록: '+JSON.stringify(j.trace.tool_calls));
 m.value='';};
</script></body></html>"""


class App:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(app_authz=settings.app_authz)
        self.retriever = Retriever(settings.fixtures_dir)
        self.bot = make_bot(settings, self.store)

    def chat(self, body, repeat):
        session = body.get("session", "")
        message = body.get("message", "")
        history = body.get("history") or []
        if not isinstance(message, str) or not message.strip():
            return 400, {"error": "message가 비어 있습니다."}
        if not isinstance(history, list) or len(history) > 20:
            return 400, {"error": "history는 20턴 이하의 목록이어야 합니다."}
        customer = self.store.customer_for_session(session)
        if customer is None:
            return 401, {"error": "알 수 없는 세션입니다. sess-A-FAKE / sess-B-FAKE / sess-C-FAKE 중 하나를 쓰세요."}
        request_id = "req-" + uuid.uuid4().hex[:12]
        docs = self.retriever.search(message)
        ctx = {
            "request_id": request_id,
            "customer": customer,
            "message": message,
            "history": [h for h in history if isinstance(h, dict) and h.get("role") in ("user", "assistant")],
            "docs": docs,
            "repeat": repeat,
            "calls": [],
        }
        try:
            reply = self.bot.respond(ctx)
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            return 502, {"error": f"모델 호출 실패: {type(exc).__name__}", "request_id": request_id}
        out = {"reply": reply, "request_id": request_id}
        if self.settings.expose_trace:
            out["trace"] = {
                "tool_calls": ctx["calls"],
                "retrieved_docs": [d["name"] for d in docs],
                "fixtures_enabled": self.retriever.fixtures_enabled,
                **self.settings.public_summary(),
            }
        return 200, out


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GanadaBot/1.0"

        def log_message(self, fmt, *args):
            if app.settings.access_log:
                sys.stderr.write("[bot] " + (fmt % args) + "\n")

        def _send(self, status, payload, content_type="application/json; charset=utf-8"):
            data = payload.encode("utf-8") if isinstance(payload, str) else \
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return None
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            return data if isinstance(data, dict) else None

        def _admin_ok(self):
            return app.settings.admin_endpoints and self.client_address[0] in ("127.0.0.1", "::1")

        def do_GET(self):
            if self.path == "/":
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if self.path == "/health":
                return self._send(200, {"status": "ok", **app.settings.public_summary(),
                                        "fixtures_enabled": app.retriever.fixtures_enabled})
            if self.path == "/admin/tool-log":
                if not self._admin_ok():
                    return self._send(404, {"error": "not found"})
                return self._send(200, {"tool_calls": app.store.tool_log[-50:]})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            body = self._body()
            if body is None:
                return self._send(400, {"error": "JSON 본문이 필요합니다(32KB 이하)."})
            if self.path == "/chat":
                try:
                    repeat = int(self.headers.get("X-Eval-Repeat") or 0)
                except ValueError:
                    repeat = 0
                status, payload = app.chat(body, repeat)
                return self._send(status, payload)
            if self.path.startswith("/admin/"):
                if not self._admin_ok():
                    return self._send(404, {"error": "not found"})
                if self.path == "/admin/fixtures":
                    app.retriever.set_fixtures(body.get("enabled"))
                    return self._send(200, {"fixtures_enabled": app.retriever.fixtures_enabled})
                if self.path == "/admin/reset":
                    app.store.reset()
                    app.retriever.set_fixtures(False)
                    return self._send(200, {"reset": True})
            return self._send(404, {"error": "not found"})

    return Handler


def serve(settings=None):
    settings = settings or Settings()
    app = App(settings)
    httpd = ThreadingHTTPServer((settings.host, settings.port), make_handler(app))
    return app, httpd


def main():
    settings = Settings()
    _, httpd = serve(settings)
    s = settings.public_summary()
    print(f"가나다몰 상담 챗봇: http://{settings.host}:{settings.port}  "
          f"(모드 {s['mode']}, 프롬프트 {s['prompt_version']}, 앱 권한 확인 {'켬' if s['app_authz'] else '끔'})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
