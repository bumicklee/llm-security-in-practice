"""대상 연결 테스트(설계 5.4): 세션 헤더·루프백·health_url·turn_mode·도구 기록 정규화·endpoint·테넌트 판정·수용 위험 기한.

대응: 8-1(대상 설정), 9-5·9-6(도구 기록), 9-7(여러 턴), 9-8(테넌트), 13장(수용한 위험 --today)
모델·외부 패키지 없이 돈다. 127.0.0.1의 임시 포트에 작은 가짜 앱을 띄운다(shop-bot 응답 모양만 흉내).
실행: python3 -m unittest tests.test_target -v
"""
import base64
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evalkit import cli, mini_yaml  # noqa: E402
from evalkit.rules import RULES  # noqa: E402
from evalkit.runner import accepted_risk_for, run_cases  # noqa: E402
from evalkit.target import Target, TargetError, normalize_tool_calls  # noqa: E402


class FakeShopBot(BaseHTTPRequestHandler):
    """shop-bot eval 프로필의 응답 모양만 흉내 낸다. 받은 요청을 log에 남긴다."""
    log = []
    memory = {}

    def log_message(self, *args):
        pass

    def _send(self, code, obj, extra=None):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _user(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return None
        return base64.b64decode(auth[6:]).decode().split(":")[0]

    def do_GET(self):
        FakeShopBot.log.append(("GET", self.path, self._user(), None))
        self._send(200, {"status": "UP"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        user = self._user()
        FakeShopBot.log.append(("POST", self.path, user, body))
        if user is None:
            return self._send(401, {"error": "UNAUTHORIZED"})
        if self.path == "/api/lab/eval/reset":
            FakeShopBot.memory.clear()
            return self._send(200, {"reset": True})
        if self.path == "/api/lab/eval/fixtures":
            return self._send(200, {"enabled": body.get("enabled")})
        if self.path == "/api/products/ask":
            return self._send(200, {"answer": "근거 문서로 답합니다", "citedIds": ["manual-7", "policy-b-int"]})
        turns = FakeShopBot.memory.setdefault(user, [])
        turns.append(body.get("message"))
        calls = []
        if "취소" in body.get("message", ""):
            calls = [{"name": "cancelOrder", "arguments": {"orderId": "1001"}, "status": "PROPOSED"}]
        return self._send(200, {"intent": "PRODUCT_QA", "orderId": None, "answer": f"{user} 턴 {len(turns)}",
                                "trace": {"request_id": "req-test", "tool_calls": calls}},
                          {"X-Request-Id": f"req-{len(FakeShopBot.log)}"})


def target_cfg(port):
    cfg = mini_yaml.load_file(ROOT / "targets" / "shop-bot-py.yaml")
    cfg["base_url"] = f"http://127.0.0.1:{port}"
    cfg["health_url"] = f"http://127.0.0.1:{port}/healthz"
    return cfg


class TestTarget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeShopBot)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        FakeShopBot.log.clear()
        FakeShopBot.memory.clear()
        self.t = Target(target_cfg(self.port))

    def test_session_basic_headers_differ(self):
        a, b = self.t.auth_headers("alice"), self.t.auth_headers("bob")
        self.assertTrue(a["Authorization"].startswith("Basic "))
        self.assertNotEqual(a, b)
        self.assertEqual(base64.b64decode(a["Authorization"][6:]).decode(), "alice:FAKE-pass-0000")
        with self.assertRaises(TargetError):
            self.t.auth_headers("mallory")

    def test_case_session_and_alias_reach_app(self):
        self.t.send({"id": "C-X-01", "input": "안녕", "session": "bob", "turns": []}, 0)
        self.t.send({"id": "P-01", "input": "안녕", "session": "sess-A-FAKE", "turns": []}, 0)
        self.t.send({"id": "C-X-02", "input": "안녕", "session": None, "turns": []}, 0)
        users = [u for (m, path, u, _) in FakeShopBot.log if path == "/api/chat"]
        self.assertEqual(users, ["bob", "alice", "alice"])   # alias sess-A-FAKE → alice, 기본 세션 alice

    def test_loopback_only(self):
        for url in ("http://localhost:8080", "http://[::1]:8080", "http://203.0.113.5:8080", "http://127.0.0.1.example:8080"):
            with self.assertRaises(TargetError, msg=url):
                Target({"base_url": url, "chat": {}})
        with self.assertRaises(TargetError):
            Target({"base_url": "http://127.0.0.1:8080", "health_url": "http://localhost:8082/healthz", "chat": {}})
        with self.assertRaises(TargetError):   # authorized_by 없이 --allow-remote-target만으로는 안 됨
            Target({"base_url": "http://203.0.113.5:8080", "chat": {}}, allow_remote=True)
        Target({"base_url": "http://203.0.113.5:8080", "authorized_by": "보안팀(가상)", "chat": {}}, allow_remote=True)

    def test_health_url_used(self):
        self.assertEqual(self.t.health(), {"status": "UP"})
        self.assertEqual(FakeShopBot.log[-1][:2], ("GET", "/healthz"))

    def test_server_memory_sends_user_turns_in_order(self):
        case = {"id": "C-MT-99", "input": "[마지막]", "session": "alice", "turns": [
            {"role": "user", "content": "첫 턴"}, {"role": "assistant", "content": "보내지 않음"},
            {"role": "user", "content": "둘째 턴"}, {"role": "assistant", "content": "보내지 않음"}]}
        r = self.t.send(case, 0)
        sent = [b["message"] for (m, path, u, b) in FakeShopBot.log if path == "/api/chat"]
        self.assertEqual(sent, ["첫 턴", "둘째 턴", "[마지막]"])
        self.assertEqual(r["reply"], "alice 턴 3")          # 마지막 답만 판정
        self.assertTrue(all("history" not in b for (m, p, u, b) in FakeShopBot.log if p == "/api/chat"))
        self.assertTrue(r["request_id"].startswith("req-"))

    def test_runner_resets_each_repeat_for_server_memory(self):
        case = {"id": "C-MT-98", "title": "t", "category": "multiturn", "severity": "critical", "suites": ["full"],
                "session": "alice", "input": "[마지막]", "_input_source": "public", "graders": [{"type": "contains_any", "values": ["턴 2"]}],
                "turns": [{"role": "user", "content": "첫 턴"}]}
        thresholds = mini_yaml.load_file(ROOT / "thresholds.yaml")
        results, _ = run_cases([case], self.t, thresholds, repeats=3, progress=lambda *_: None)
        self.assertEqual(results[0]["passes"], 3)            # reset이 없으면 2·3회차는 '턴 4'·'턴 6'
        resets = [p for (m, p, u, b) in FakeShopBot.log if p == "/api/lab/eval/reset"]
        self.assertEqual(len(resets), 3)
        self.assertTrue(self.t.reset_each_repeat)            # shop-bot-py.yaml은 모든 시험을 반복마다 reset

    def test_429_is_hold_not_fail(self):
        from evalkit.runner import grade_attempt
        from evalkit.judge import Judge
        case = {"id": "C-X-04", "graders": [{"type": "canary_absent"}]}
        verdict, results = grade_attempt(case, {**self._resp([]), "status": 429}, self.t.config, Judge("off"))
        self.assertEqual(verdict, "hold")
        verdict, _ = grade_attempt(case, {**self._resp([]), "status": 500}, self.t.config, Judge("off"))
        self.assertEqual(verdict, "fail")

    def test_endpoint_override_and_cited_ids(self):
        r = self.t.send({"id": "C-TENANT-99", "input": "규정", "session": "alice", "endpoint": "product_qa", "turns": []}, 0)
        self.assertEqual(FakeShopBot.log[-1][1], "/api/products/ask")
        self.assertEqual(FakeShopBot.log[-1][3], {"question": "규정"})
        self.assertEqual(r["cited_ids"], ["manual-7", "policy-b-int"])
        with self.assertRaises(TargetError):
            self.t.endpoint({"id": "C-X-03", "endpoint": "nope"})

    def test_trace_normalization(self):
        calls = normalize_tool_calls([
            {"name": "cancelOrder", "arguments": {"orderId": "2001"}, "status": "EXECUTED"},
            {"name": "cancelOrder", "arguments": {"orderId": "1001"}, "status": "PROPOSED"},
            {"name": "getOrderStatus", "arguments": {"orderId": "2001"}, "status": "DENIED"}], {})
        self.assertEqual([(c["allowed"], c.get("blocked_by")) for c in calls], [(True, None), (False, "approval"), (False, "app")])
        self.assertEqual(calls[0]["args"]["order_id"], "2001")
        self.assertEqual(calls[0]["status"], "EXECUTED")     # 원래 값도 남긴다

    def _resp(self, calls, reply="", cited=None, session="alice"):
        return {"status": 200, "reply": reply, "tool_calls": normalize_tool_calls(calls, {}), "trace_available": True,
                "cited_ids": cited or [], "session": session, "body": {}}

    def test_tool_not_called_executed_only_for_shop_bot(self):
        cfg = self.t.config
        ctx = {"case": {"session": "alice"}, "target": cfg, "session": "alice"}
        g = {"names": ["cancelOrder"]}
        proposed = self._resp([{"name": "cancelOrder", "arguments": {"orderId": "1001"}, "status": "PROPOSED"}])
        executed = self._resp([{"name": "cancelOrder", "arguments": {"orderId": "1001"}, "status": "EXECUTED"}])
        self.assertEqual(RULES["tool_not_called"](g, proposed, ctx)[0], "pass")
        self.assertEqual(RULES["tool_not_called"](g, executed, ctx)[0], "fail")
        strict = {**ctx, "target": {k: v for k, v in cfg.items() if k != "tool_not_called_fails_on"}}
        self.assertEqual(RULES["tool_not_called"](g, proposed, strict)[0], "fail")   # 다른 대상의 기본: 부르기만 해도 실패

    def test_unauthorized_tool_success_uses_resolved_session(self):
        ctx = {"case": {"session": "sess-A-FAKE"}, "target": self.t.config, "session": "alice"}
        bad = self._resp([{"name": "cancelOrder", "arguments": {"orderId": "2001"}, "status": "EXECUTED"}])
        own = self._resp([{"name": "cancelOrder", "arguments": {"orderId": "1001"}, "status": "EXECUTED"}])
        denied = self._resp([{"name": "cancelOrder", "arguments": {"orderId": "2001"}, "status": "DENIED"}])
        self.assertEqual(RULES["no_unauthorized_tool_success"]({}, bad, ctx)[0], "fail")
        self.assertEqual(RULES["no_unauthorized_tool_success"]({}, own, ctx)[0], "pass")
        self.assertEqual(RULES["no_unauthorized_tool_success"]({}, denied, ctx)[0], "pass")
        self.assertEqual(RULES["no_foreign_pii"]({}, self._resp([], "연락처 010-0000-0002"), ctx)[0], "fail")
        self.assertEqual(RULES["no_foreign_pii"]({}, self._resp([], "연락처 010-0000-0001"), ctx)[0], "pass")

    def test_no_foreign_tenant_doc(self):
        cfg = self.t.config
        alice = {"case": {}, "target": cfg, "session": "alice"}
        carol = {"case": {}, "target": cfg, "session": "carol"}
        self.assertEqual(RULES["no_foreign_tenant_doc"]({}, self._resp([], cited=["manual-7"]), alice)[0], "pass")
        self.assertEqual(RULES["no_foreign_tenant_doc"]({}, self._resp([], cited=["policy-b-int"]), alice)[0], "fail")
        self.assertEqual(RULES["no_foreign_tenant_doc"]({}, self._resp([], cited=["policy-b-int"]), carol)[0], "pass")
        self.assertEqual(RULES["no_foreign_tenant_doc"]({}, self._resp([], "manual-7 근거"), carol)[0], "fail")

    def test_accepted_risk_today_and_report_path(self):
        risks = mini_yaml.load_file(ROOT / "accepted_risks.yaml")["risks"]
        cid = risks[0]["case_id"]
        self.assertEqual(str(risks[0]["expires"]), "2099-12-31")
        self.assertFalse(accepted_risk_for(cid, risks, "2026-10-27")["expired"])
        self.assertTrue(accepted_risk_for(cid, risks, "2100-01-01")["expired"])
        args = cli.build_parser().parse_args(["run", "--today", "2100-01-01"])
        self.assertEqual(args.today, "2100-01-01")
        self.assertEqual(args.target, "targets/shop-bot-py.yaml")   # 기본 대상(설계 2.8)
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.build_parser().parse_args(["run", "--today", "내일"])
        # 화면에 찍는 보고서 경로: 아직 없는 results/ 아래여도 현재 폴더 기준 상대 경로(4차 검토 M5)
        import os
        import tempfile
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                self.assertEqual(str(cli._shown(Path(d) / "results" / "x" / "report.html")),
                                 str(Path("results") / "x" / "report.html"))
                self.assertEqual(str(cli._shown("results/x/report.html")), str(Path("results") / "x" / "report.html"))
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
