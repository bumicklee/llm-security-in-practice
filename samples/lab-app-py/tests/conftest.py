"""pytest 공용 설정.

pytest --lab-target=before  → labcore 공격 테스트가 수정 전 구현을 본다(빨강), tests/app은 LAB_PROFILES=before
pytest                      → 수정 후(초록)
표식: capstone(22장 종합 실습, `-m capstone`), contract(HTTP 계약·가짜 LLM 녹화 답 대조, `-m contract`). 둘 다 기본 실행에서 뺀다
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_addoption(parser):
    parser.addoption("--lab-target", action="store", default="after", choices=["after", "before"],
                     help="after(수정 후, 기본) | before(수정 전: 취약점 재현)")


def pytest_configure(config):
    os.environ["LAB_TARGET"] = config.getoption("--lab-target")


def pytest_report_header(config):
    from labcore import target
    return f"lab-target: {target.name()}"
