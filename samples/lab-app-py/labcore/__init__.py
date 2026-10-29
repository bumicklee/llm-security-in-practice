"""labcore — 순수 Python 방어 코드와 수정 전/후 쌍.

FastAPI·LangChain·네트워크 없이 돈다. 그래서 pytest가 결정적이다(설계 2.1 원칙 2).
하위 패키지: injection · rag · cost · tools · ssrf · output · audit · llm
"""
from labcore.user import UserContext

__all__ = ["UserContext"]
