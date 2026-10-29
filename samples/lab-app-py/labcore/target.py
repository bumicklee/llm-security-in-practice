"""공격 테스트가 "수정 전" 구현을 볼지 "수정 후" 구현을 볼지 고른다.

실행: pytest tests/attack tests/unit --lab-target=before   → 빨강(취약점 재현)
      pytest tests/attack tests/unit                       → 초록(방어 증명)
conftest가 환경 변수 LAB_TARGET을 넣는다. 대응 장: 2장 2.3, 12장 12.2
"""
import os


def is_before() -> bool:
    return os.environ.get("LAB_TARGET", "after").strip().lower() == "before"


def name() -> str:
    return "before(수정 전)" if is_before() else "after(수정 후)"
