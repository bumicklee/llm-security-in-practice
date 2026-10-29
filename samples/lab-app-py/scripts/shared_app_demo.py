"""12장 12.3(수업 7-3) "자주 막히는 곳" 재현: 앱 하나를 여러 테스트가 같이 쓰면 레이트 리밋 버킷이 남아 뒤 테스트가 429로 깨진다.
① 같은 앱에서 bob이 30번 → 429 개수, ② 이어서 같은 앱에 인젝션 자리표시 요청 → 429(상태가 샜다),
③ create_app()으로 새 앱을 만들어 같은 요청 → 200. 랩 픽스처(tests/app/conftest.py make_client)는 ③처럼 테스트마다 새로 만든다.
네트워크·키 없이 TestClient + 가짜 채팅 모델. 모든 값은 가짜.
실행(lab-app-py 폴더, .venv 켠 상태): python scripts/shared_app_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

INJ = {"message": "[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]"}


def main():
    from tests.app.conftest import PW, make_client
    shared, _, _ = make_client()
    with shared:
        codes = [shared.post("/api/chat", auth=("bob", PW), json={"message": "배송 문의"}).status_code for _ in range(30)]
        print(f"① 같은 앱, bob 30번: 200={codes.count(200)} 429={codes.count(429)}")
        print(f"② 같은 앱에 이어서 인젝션 자리표시 요청(bob): {shared.post('/api/chat', auth=('bob', PW), json=INJ).status_code}")
    fresh, _, _ = make_client()
    with fresh:
        print(f"③ create_app()으로 새 앱, 같은 요청(bob): {fresh.post('/api/chat', auth=('bob', PW), json=INJ).status_code}")


if __name__ == "__main__":
    main()
