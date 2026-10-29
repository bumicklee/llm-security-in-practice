"""promptfoo 변환 테스트 — 05 A 리뷰 F1(로컬 채점 모델)·F2(기준표 출력 형식 줄 제거)·F7(버전 고정). 대응: 11장"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evalkit import mini_yaml, promptfoo_export  # noqa: E402
from evalkit.cases import load_cases  # noqa: E402
from evalkit.judge import load_rubrics  # noqa: E402


class TestPromptfooExport(unittest.TestCase):
    def setUp(self):
        self.cases, errors = load_cases([ROOT / "cases"])
        self.assertEqual(errors, [])
        self.target = mini_yaml.load_file(ROOT / "targets" / "shop-bot-py.yaml")
        self.rubrics = load_rubrics(ROOT / "judge" / "rubrics")

    def test_local_grader_provider(self):
        config, _ = promptfoo_export.convert(self.cases, self.target, self.rubrics, env={})
        prov = config["defaultTest"]["options"]["provider"]
        self.assertTrue(prov["id"].startswith("openai:chat:"))
        self.assertEqual(prov["config"]["apiBaseUrl"], "http://127.0.0.1:1234/v1")
        with self.assertRaises(ValueError):
            promptfoo_export.convert(self.cases, self.target, self.rubrics, env={"JUDGE_BASE_URL": "https://api.example.com/v1"})

    def test_rubric_has_criteria_only(self):
        config, _ = promptfoo_export.convert(self.cases, self.target, self.rubrics, env={})
        rubrics = [a["value"] for t in config["tests"] for a in t["assert"] if a["type"] == "llm-rubric"]
        self.assertTrue(rubrics)
        for r in rubrics:
            self.assertNotIn("출력은 JSON", r)
            self.assertNotIn("verdict", r)
            self.assertIn("pass:", r)

    def test_shop_bot_provider_and_skips(self):
        config, skipped = promptfoo_export.convert(self.cases, self.target, self.rubrics, env={})
        p = config["providers"][0]["config"]
        self.assertEqual(p["url"], "http://127.0.0.1:8080/api/chat")
        self.assertEqual(p["body"], {"message": "{{prompt}}"})
        self.assertEqual(p["transformResponse"], "json.answer")
        self.assertEqual(p["headers"]["Authorization"], "{{auth}}")
        why = {s["id"]: s["graders"] for s in skipped}
        self.assertIn("endpoint:product_qa", why["C-TENANT-01"])
        self.assertIn("turns(server_memory)", why["C-MT-01"])
        self.assertIn("tool_not_called", why["C-TOOL-01"])
        self.assertTrue(all(t["vars"]["auth"].startswith("Basic ") for t in config["tests"]))

    def test_version_pinned_in_header(self):
        import tempfile
        config, skipped = promptfoo_export.convert(self.cases[:3], self.target, self.rubrics, env={})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "pf.yaml"
            promptfoo_export.write(config, skipped, out)
            head = out.read_text(encoding="utf-8")[:600]
        self.assertIn("promptfoo@0.125.1", head)
        self.assertIn("22.22.0", head)


if __name__ == "__main__":
    unittest.main()
