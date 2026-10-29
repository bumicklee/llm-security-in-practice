"""끝에서 끝까지: 다른 스택(파이썬 스텁 support-bot)을 띄우고 portable 시험 5문제와 게이트를 돌린다.

대응 장: 13-6(다른 스택에 붙이기), 12장(빨간불 보기). 모델 없이, 외부 패키지 없이 돈다.
shop-bot-py 쪽 끝에서 끝까지는 앱을 띄워야 하므로 _실측/8-2_*·9-*_*(수정 전 RED / 수정 후 GREEN)로 남긴다.
실행: python3 -m unittest tests.test_e2e_stub -v

상담봇 위치(앞에서부터 처음 있는 것): 환경 변수 SUPPORT_BOT_DIR → lab-app-py/extras/support-bot-python
→ 저장소 루트(llm-security-in-practice)의 samples/extras/support-bot-python. 셋 다 없으면(랩 폴더만 저장소로 올린 경우) 상담봇을 띄우는
4개는 건너뛴다(skip, 실패 아님). 대상 주소 거부 시험 1개는 상담봇 없이 늘 돈다(2차 교차 검증 B F-02).
"""
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_bot():
    env = os.environ.get("SUPPORT_BOT_DIR")
    for p in ([Path(env)] if env else []) + [ROOT.parent / "extras" / "support-bot-python",
                                            ROOT.parents[1] / "extras" / "support-bot-python"]:
        if (p / "app.py").is_file() and (p / "config.py").is_file():
            return p.resolve()
    return None


BOT = find_bot()
sys.path.insert(0, str(ROOT))
if BOT is not None:
    sys.path.insert(0, str(BOT))

from evalkit import mini_yaml  # noqa: E402
from evalkit.cases import load_cases  # noqa: E402
from evalkit.judge import Judge, load_rubrics  # noqa: E402
from evalkit.runner import gate_decision, run_cases  # noqa: E402
from evalkit.target import Target, TargetError  # noqa: E402


def start_bot(profile, authz="on"):
    import app as bot_app  # extras/support-bot-python/app.py
    from config import Settings
    _, httpd = bot_app.serve(Settings({"BOT_PORT": "0", "BOT_PROFILE": profile, "APP_AUTHZ": authz, "BOT_ACCESS_LOG": "0"}))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run(profile, folder, authz="on", judge="off"):
    httpd = start_bot(profile, authz)
    try:
        cfg = mini_yaml.load_file(ROOT / "targets" / "support-bot-python.yaml")
        cfg["base_url"] = f"http://127.0.0.1:{httpd.server_address[1]}"
        target = Target(cfg)
        cases, errors = load_cases([ROOT / "cases" / folder])
        assert not errors, errors
        thresholds = mini_yaml.load_file(ROOT / "thresholds.yaml")
        results, _ = run_cases(cases, target, thresholds, Judge(judge, load_rubrics(ROOT / "judge" / "rubrics")),
                               repeats=1, progress=lambda *_: None)
        return results, gate_decision(results)
    finally:
        httpd.shutdown()
        httpd.server_close()


@unittest.skipIf(BOT is None, "support-bot-python 없음(랩 폴더만 있는 저장소) → SUPPORT_BOT_DIR로 위치를 주면 돈다")
class TestEndToEnd(unittest.TestCase):
    def test_portable_v1_red(self):
        results, gate = run("v1", "portable")
        self.assertEqual(sorted(c["id"] for c in results if c["status"] == "fail"), ["P-02", "P-03", "P-05"])
        self.assertEqual(gate["color"], "red")

    def test_portable_v4_green(self):
        _, gate = run("v4", "portable")
        self.assertEqual(gate["color"], "green")

    def test_v3_overrefusal_is_yellow_not_red(self):
        _, gate = run("v3", "portable")
        self.assertEqual(gate["color"], "yellow")
        self.assertEqual(gate["red"], [])

    def test_authz_off_adds_foreign_pii_failure(self):
        _, on = run("v1", "portable")
        _, off = run("v1", "portable", authz="off")
        self.assertNotIn("P-04", on["red"])
        self.assertIn("P-04", off["red"])


class TestTargetGuard(unittest.TestCase):
    def test_remote_target_refused(self):
        with self.assertRaises(TargetError):
            Target({"base_url": "https://example.com", "chat": {}})


if __name__ == "__main__":
    unittest.main()
