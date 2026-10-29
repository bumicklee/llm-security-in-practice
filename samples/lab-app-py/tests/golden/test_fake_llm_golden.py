"""가짜 LLM 녹화 답 대조 시험(설계 2.5, -m contract). 녹화해 둔 요청·응답 쌍을 가짜 LLM(tools/fake_llm.py)에 다시 보낸다.

가짜 LLM의 규칙을 고치다가 답이 몰래 바뀌면(수업 화면·_실측과 어긋나면) 이 시험이 빨개진다.
비교: 상태 코드 + JSON 본문(id·created 제외, /usage의 perSecond 제외). JSON이 아니면 글자 그대로.
녹화: scripts/record_fake_llm_golden.py(규칙을 일부러 바꾼 뒤에만 다시 녹화한다).
실행: pytest -m contract tests/golden -v
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tools" / "_golden" / "fake_llm_cases.jsonl"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(env_extra=None):
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAKE_LLM_")}
    env.update({"FAKE_LLM_PORT": str(port), "BIND": "127.0.0.1"}, **(env_extra or {}))
    p = subprocess.Popen([sys.executable, "-I", str(ROOT / "tools" / "fake_llm.py")], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/v1/models", timeout=1).read()
            return p, base
        except OSError:
            time.sleep(0.05)
    p.kill()
    raise RuntimeError("가짜 LLM이 뜨지 않음")


def _send(base, method, path, body):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _normalize(text):
    try:
        v = json.loads(text)
    except ValueError:
        return text
    if isinstance(v, dict):
        v.pop("id", None)
        v.pop("created", None)
        v.pop("perSecond", None)
    return v


@pytest.fixture(scope="module")
def py_server():
    p, base = _start()
    yield base
    p.terminate()
    p.wait(5)


def _golden():
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_골든_쌍은_60개_안팎이다():
    assert 55 <= len(_golden()) <= 80


def test_가짜_LLM은_녹화해_둔_답과_같은_답을_낸다(py_server):
    diffs, same_bytes = [], 0
    for g in _golden():
        status, text = _send(py_server, g["method"], g["path"], g["body"])
        if status != g["status"] or _normalize(text) != _normalize(g["response"]):
            diffs.append((g["name"], g["status"], status, g["response"][:200], text[:200]))
        elif text.replace(text.split('"id":"', 1)[-1].split('"', 1)[0], "") == \
                g["response"].replace(g["response"].split('"id":"', 1)[-1].split('"', 1)[0], ""):
            same_bytes += 1
    print(f"\n대조 {len(_golden())}쌍 · 다름 {len(diffs)} · 바이트까지 같음(id 제외) {same_bytes}")
    assert diffs == []


def test_흔들림_모드는_같은_씨앗이면_같은_순서를_낸다():
    def run():
        p, base = _start({"FAKE_LLM_WOBBLE": "0.5", "FAKE_LLM_SEED": "42"})
        try:
            body = {"messages": [{"role": "system", "content": "할인 코드 FAKE-VIP-2026"},
                                 {"role": "user", "content": "[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]"}]}
            return ["X" if "FAKE-VIP-2026" in _send(base, "POST", "/v1/chat/completions", body)[1] else "."
                    for _ in range(20)]
        finally:
            p.terminate()
            p.wait(5)
    first, second = run(), run()
    assert first == second
    assert "X" in first and "." in first   # 0.5면 둘 다 나온다
