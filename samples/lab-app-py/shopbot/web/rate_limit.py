"""모델을 부르는 엔드포인트(/api/chat, /api/products/ask*)에 사용자별 레이트 리밋(8장 8.1).

키 = 로그인 사용자 ID("user:<id>"). IP가 아니다: slowapi는 key_func가 필수 인자라 기본 키가 없지만, 흔히 넘기는 get_remote_address가 IP 기준이라 쓰려면 key_func를 사용자 ID로 준다.
넘으면 429 + Retry-After. 모델 호출 전이므로 토큰 0. 저장소: 기본은 labcore 토큰 버킷(메모리), redis 프로필은 limits + Redis.
"""
from fastapi import Depends, HTTPException, Response

from labcore.cost import RateResult
from labcore.user import UserContext
from shopbot.security import current_user
from shopbot.state import LabState, get_lab


class RateLimited(HTTPException):
    pass


class LimitsRedisLimiter:
    """redis 프로필: limits 5.8.0(MovingWindow + Redis 저장소). 여러 서버가 한 버킷을 나눠 쓴다."""

    def __init__(self, redis_url: str, per_minute: int):
        from limits import RateLimitItemPerMinute
        from limits.storage import storage_from_string
        from limits.strategies import MovingWindowRateLimiter
        self._storage = storage_from_string(redis_url)
        self._limiter = MovingWindowRateLimiter(self._storage)
        self._item = RateLimitItemPerMinute(per_minute)

    def try_acquire(self, key: str) -> RateResult:
        ok = self._limiter.hit(self._item, "lab", key)
        stats = self._limiter.get_window_stats(self._item, "lab", key)
        import time
        retry = max(1, int(stats.reset_time - time.time())) if not ok else 0
        return RateResult(ok, stats.remaining, retry)

    def reset(self) -> None:
        self._storage.reset()


def rate_limited_user(response: Response, user: UserContext = Depends(current_user),
                      lab: LabState = Depends(get_lab)) -> UserContext:
    if not lab.settings.defense.rate_limit:
        return user
    r = lab.limiter.try_acquire("user:" + user.user_id)
    if not r.allowed:
        raise RateLimited(status_code=429, detail={"error": "RATE_LIMITED", "retryAfterSeconds": r.retry_after_seconds},
                          headers={"Retry-After": str(r.retry_after_seconds), "X-RateLimit-Remaining": str(r.remaining)})
    response.headers["X-RateLimit-Remaining"] = str(r.remaining)
    return user
