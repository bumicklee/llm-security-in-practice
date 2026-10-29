"""로그인(HTTP Basic)과 랩 사용자. 권한 판단은 이 값으로만 한다.

가짜 사용자: alice·bob(shop-a 고객), dave(shop-a 직원), carol(shop-b 직원). 비밀번호는 모두 FAKE-pass-0000(랩 전용).
채팅 API는 로그인한 사용자만(7장: 로그인 없이 열린 챗봇 = 누구나 내 키로 모델을 부르는 통로).
"""
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from labcore.user import UserContext

FAKE_PASSWORD = "FAKE-pass-0000"   # 가짜 비밀번호. 실서비스 금지


class LabUsers:
    def __init__(self):
        self._users = {"alice": UserContext.alice(), "bob": UserContext.bob(),
                       "carol": UserContext.carol(), "dave": UserContext.dave()}
        # 가짜 연락처(010-0000-000N, *.example). 남의 데이터 시험(9-3)의 등록부 값과 같다
        self._contacts = {"alice": "010-0000-0001 alice@shop-a.example", "bob": "010-0000-0002 bob@shop-a.example",
                          "carol": "010-0000-0003 carol@shop-b.example", "dave": "010-0000-0004 dave@shop-a.example"}

    def contact_of(self, user_id: str) -> str | None:
        return self._contacts.get(user_id)

    def user_ids(self) -> list[str]:
        return list(self._users)

    def get(self, name: str) -> UserContext | None:
        return self._users.get(name)


LAB_USERS = LabUsers()   # 바뀌지 않는 시드 값(상태 없음)이라 모듈에 둬도 테스트끼리 섞이지 않는다
_basic = HTTPBasic(auto_error=False)


def authenticate(credentials: HTTPBasicCredentials | None) -> UserContext:
    user = LAB_USERS.get(credentials.username) if credentials else None
    ok = user is not None and secrets.compare_digest(credentials.password.encode(), FAKE_PASSWORD.encode())
    if not ok:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED", headers={"WWW-Authenticate": 'Basic realm="Realm"'})
    return user


def current_user(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> UserContext:
    return authenticate(credentials)
