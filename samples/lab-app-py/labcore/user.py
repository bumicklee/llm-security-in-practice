"""로그인한 사용자 정보. 권한 판단은 언제나 이 값(서버가 아는 사실)으로 한다.

모델이 넘긴 인자나 사용자가 채팅에 쓴 테넌트 이름으로 판단하지 않는다.
staff=True(직원)만 같은 테넌트의 INTERNAL 문서를 볼 수 있다(6장 표 6-1). 대응 장: 6장, 9장
"""
import re
from dataclasses import dataclass

_ID = re.compile(r"[a-z0-9-]{1,32}")


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str
    vip: bool = False
    staff: bool = False

    def __post_init__(self):
        if self.user_id is None or self.tenant_id is None:
            raise TypeError("userId·tenantId는 비울 수 없다")
        if not _ID.fullmatch(self.user_id) or not _ID.fullmatch(self.tenant_id):
            raise ValueError("허용되지 않은 ID 형식")

    @staticmethod
    def alice() -> "UserContext":   # shop-a 고객
        return UserContext("alice", "shop-a")

    @staticmethod
    def bob() -> "UserContext":     # shop-a 고객
        return UserContext("bob", "shop-a")

    @staticmethod
    def carol() -> "UserContext":   # shop-b 직원
        return UserContext("carol", "shop-b", staff=True)

    @staticmethod
    def dave() -> "UserContext":    # shop-a 직원(6장 장면)
        return UserContext("dave", "shop-a", staff=True)
