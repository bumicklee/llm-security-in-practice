"""앱 테스트 공용: 테스트마다 create_app()으로 새 앱을 만든다(12.3).

앱을 여러 테스트가 같이 쓰면 앞 테스트가 비운 레이트 리밋 버킷이 남아 다른 테스트가 429로 실패한다. 그 실패를 구조로 막는다.
가짜 채팅 모델은 app.dependency_overrides[get_chat_model]로 넣는다(키·네트워크 불필요).
--lab-target=before 이면 LAB_PROFILES=before(수정 전) 앱을 만든다.
"""
import pytest
from fastapi.testclient import TestClient

from labcore import target
from shopbot.main import create_app
from shopbot.settings import load_settings
from shopbot.state import get_chat_model
from tests.app.stub_model import StubChatModel

PW = "FAKE-pass-0000"


def make_client(*profiles: str, client_host: str = "127.0.0.1"):
    names = (["before"] if target.is_before() else []) + list(profiles)
    app = create_app(load_settings(names, env={}, side_servers=False, admin_page_enabled=False))
    stub = StubChatModel()
    app.dependency_overrides[get_chat_model] = lambda: stub
    return TestClient(app, client=(client_host, 50000)), stub, app.state.lab


@pytest.fixture
def bot():
    c, stub, lab = make_client()
    with c:
        yield c, stub, lab


@pytest.fixture
def eval_bot():
    c, stub, lab = make_client("eval")
    with c:
        yield c, stub, lab


def auth(user):
    return (user, PW)
