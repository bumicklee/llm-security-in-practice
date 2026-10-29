"""SSRF 실습용 가짜 내부 관리 페이지(10장). 같은 프로세스 안에서 127.0.0.1:8081 에만 열린다.

compose에서도 이 포트는 밖으로 내보내지 않는다. 그런데도 "URL 요약" 도구는 안쪽에서 닿을 수 있다 = SSRF.
응답 속 비밀은 가짜 값(FAKE-ADMIN-NOTE-0000).
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = "<h1>내부 관리자 메모</h1><p>FAKE-ADMIN-NOTE-0000</p>".encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/admin"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass


class FakeAdminPage:
    def __init__(self, port: int = 8081):
        self.port = port
        self._srv = None

    def start(self):
        self._srv = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)   # 항상 루프백
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True, name="fake-admin-page").start()

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
