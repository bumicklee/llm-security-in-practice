"""mini_yaml 단위 테스트 — 대응 장: 3장(3.2). 실행: python3 -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalkit import mini_yaml  # noqa: E402

DOC = '''
# 주석
id: INJ-01
title: "따옴표: 콜론 있음"
owasp: [LLM01, "LLM07"]
repeat: 3
rate: 0.9
flag: true
none: ~
setup: {fixtures: true}
graders:
  - type: canary_absent
  - type: contains_any
    values: ["7일", '일주일']
turns:
  -
    role: user
    content: 안녕하세요
system: |
  첫 줄
  둘째 줄
folded: >-
  한 줄로
  이어짐
'''


class TestMiniYaml(unittest.TestCase):
    def test_subset(self):
        d = mini_yaml.loads(DOC, force_builtin=True)
        self.assertEqual(d["id"], "INJ-01")
        self.assertEqual(d["title"], "따옴표: 콜론 있음")
        self.assertEqual(d["owasp"], ["LLM01", "LLM07"])
        self.assertEqual((d["repeat"], d["rate"], d["flag"], d["none"]), (3, 0.9, True, None))
        self.assertEqual(d["setup"], {"fixtures": True})
        self.assertEqual(d["graders"][1], {"type": "contains_any", "values": ["7일", "일주일"]})
        self.assertEqual(d["turns"][0], {"role": "user", "content": "안녕하세요"})
        self.assertEqual(d["system"], "첫 줄\n둘째 줄\n")
        self.assertEqual(d["folded"], "한 줄로 이어짐")

    def test_errors(self):
        for bad in ("a: 1\n  b: 2\n", "a: \"닫히지 않음\n", "a: &anchor 1\n", "a: 1\na: 2\n"):
            with self.assertRaises(mini_yaml.YamlError, msg=bad):
                mini_yaml.loads(bad, force_builtin=True)

    def test_dump_roundtrip(self):
        value = {"tests": [{"vars": {"input": "환불: 7일?"}, "assert": [{"type": "not-contains", "value": "X"}]}],
                 "empty": [], "n": 2}
        self.assertEqual(mini_yaml.loads(mini_yaml.dumps(value), force_builtin=True), value)


if __name__ == "__main__":
    unittest.main()
