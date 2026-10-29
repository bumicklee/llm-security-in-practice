"""1분 10번 한도를 넘으면 429, 모델 호출 수는 10을 넘지 않는다(8장 8.1, 12장 12.4).

앱을 테스트끼리 같이 쓰면 이 테스트가 비운 bob의 버킷을 다른 테스트가 물려받아 429로 실패한다.
픽스처가 테스트마다 create_app()을 새로 부르므로 버킷이 테스트 밖으로 새지 않는다.
"""
from tests.app.conftest import auth


def test_반복_호출은_429(bot):
    c, stub, _ = bot
    limited = sum(1 for _ in range(30)
                  if c.post("/api/chat", auth=auth("bob"), json={"message": "배송 문의"}).status_code == 429)
    assert limited >= 20
    assert stub.calls <= 10
