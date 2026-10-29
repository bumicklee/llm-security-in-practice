"""시험 문제 스키마·안전 규칙 테스트 — 대응 장: 3장(3.2), 1장(1.6 안전 수칙)."""
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evalkit.cases import load_cases, validate_case  # noqa: E402

GOOD = {"id": "C-BEN-99", "title": "t", "category": "benign", "severity": "low", "intent": "i",
        "input": "환불은?", "expected_behavior": "e", "graders": [{"type": "not_refusal"}]}


class TestCases(unittest.TestCase):
    def test_all_50_valid_and_counts(self):
        """shop-bot판 50개(설계 5.5). cases/를 통째로 주면 portable/·capstone/은 빠진다."""
        cases, errors = load_cases([ROOT / "cases"])
        self.assertEqual(errors, [])
        self.assertEqual(len(cases), 50)
        folders = Counter(Path(c["_file"]).parent.name for c in cases)
        self.assertEqual(dict(folders), {"starter": 5, "injection": 6, "leak-system": 6, "leak-pii": 6, "benign": 6,
                                         "indirect": 6, "tool": 5, "authz": 4, "tenant": 3, "multiturn": 3})
        self.assertTrue(all(re.match(r"^C-[A-Z]+-\d{2}$", c["id"]) for c in cases))

    def test_portable_only_when_given(self):
        cases, errors = load_cases([ROOT / "cases" / "portable"])
        self.assertEqual(errors, [])
        self.assertEqual(len(cases), 5)
        self.assertTrue(all(c["id"].startswith("P-") for c in cases))

    def test_quick_suite_has_one_multiturn(self):
        """quick 묶음: 유형마다 2~3개 + 여러 턴 1개(설계 7장 결정 12) = 21개."""
        cases, _ = load_cases([ROOT / "cases"], suite="quick")
        self.assertEqual(len(cases), 21)
        self.assertEqual([c["id"] for c in cases if c["category"] == "multiturn"], ["C-MT-01"])

    def test_capstone_only_when_given(self):
        """22장 종합 실습 6개는 cases/를 통째로 줄 때 빠지고, 경로로 줄 때만 들어온다(1~21장의 50개를 지킴)."""
        cases, errors = load_cases([ROOT / "cases" / "capstone"])
        self.assertEqual(errors, [])
        self.assertEqual(sorted(c["id"] for c in cases),
                         ["C-AUTHZ-05", "C-AUTHZ-06", "C-BEN-10", "C-MT-04", "C-TOOL-06", "C-TOOL-07"])
        both, errors = load_cases([ROOT / "cases", ROOT / "cases" / "capstone"])
        self.assertEqual((len(both), errors), (56, []))

    def test_endpoint_name_checked(self):
        self.assertEqual(validate_case(dict(GOOD, endpoint="product_qa")), [])
        self.assertTrue(validate_case(dict(GOOD, endpoint="/api/products/ask")))

    def test_attack_inputs_are_placeholders(self):
        """공개 저장소의 공격 유형 시험 문제는 모두 자리표시여야 한다."""
        cases, _ = load_cases([ROOT / "cases"])
        for c in cases:
            if c.get("input_ref"):
                self.assertTrue(re.match(r"^\[ATTACK-[A-Z]+-[A-Z0-9]+: [^\]]+\] .+자리표시|^\[ATTACK-.*비공개", c["input"]) or
                                "비공개 세트" in c["input"], c["id"])
            for t in c["turns"]:
                if t.get("ref"):
                    self.assertIn("비공개 세트", t["content"], c["id"])

    def test_missing_fields_and_placeholder_rules(self):
        self.assertEqual(validate_case(GOOD), [])
        bad = dict(GOOD)
        del bad["graders"]
        self.assertTrue(any("graders" in e for e in validate_case(bad)))
        inj = dict(GOOD, id="C-INJ-99", category="injection")
        self.assertTrue(any("input_ref" in e for e in validate_case(inj)))
        wrong_ref = dict(inj, input_ref="ATTACK-INJ-01", input="[ATTACK-INJ-02: 역할 바꾸기 유형] 자리표시")
        self.assertTrue(validate_case(wrong_ref))

    def test_private_overlay(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "attack_inputs.yaml"
            p.write_text('inputs:\n  ATTACK-INJ-01: {text: "PRIVATE-TEST-TEXT"}\n  ATTACK-INJ-02: {text: "<<미작성>>"}\n',
                         encoding="utf-8")
            cases, _ = load_cases([ROOT / "cases" / "injection"], private_path=p)
            by = {c["id"]: c for c in cases}
            self.assertEqual(by["C-INJ-01"]["_input_source"], "private")
            self.assertEqual(by["C-INJ-02"]["_input_source"], "placeholder")


if __name__ == "__main__":
    unittest.main()
