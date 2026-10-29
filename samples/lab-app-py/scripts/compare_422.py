"""4장 4.2(수업 2-4) 비교: 같은 4,000자 입력을 ① 랩 앱(넉넉한 스키마 + 입력 가드)과 ② Pydantic 길이 제약에만 맡긴 작은 앱에 보낸다.
① 400 + 정해진 본문(가드), ② 422 + FastAPI 기본 오류(string_too_long). 같은 "막힘"이라도 계약이 다르면 시험이 깨진다.
네트워크·키 없이 TestClient로 돈다(① 가짜 채팅 모델 = tests/app/stub_model.py). 모든 값은 가짜.
실행(lab-app-py 폴더, .venv 켠 상태): python scripts/compare_422.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

LONG = {"message": "가" * 4000}


class TightChatRequest(BaseModel):        # 비교용: 길이 검사를 스키마에만 맡김
    message: str = Field(..., max_length=1000)


def tight_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/chat")
    def chat(req: TightChatRequest):
        return {"answer": "닿지 않는다"}

    return app


def main():
    from tests.app.conftest import PW, make_client
    c, stub, _ = make_client()
    with c:
        r = c.post("/api/chat", auth=("bob", PW), json=LONG)
        print(f"① 랩 앱(ChatRequest max_length=200,000 + 입력 가드): {r.status_code} {r.text[:120]} · 모델 호출 {stub.calls}번")
    r = TestClient(tight_app()).post("/api/chat", json=LONG)
    detail = r.json()["detail"][0]
    print(f"② 비교 앱(TightChatRequest max_length=1000만): {r.status_code} {detail['type']}")


if __name__ == "__main__":
    main()
