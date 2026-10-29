"""캐시 적중률 전후 표(8장 8.4, 수업 4-6). labcore의 ResponseCache 두 구현에 같은 질문 순서를 흘린다.

수정 전 SharedKeyCache(키 = 정규화한 질문) / 수정 후 ScopedCache(키 = 테넌트|사용자|질문, 주문 답은 캐시 안 함).
랩 단순화: 시맨틱(비슷한 뜻) 대신 정규화 문자열 일치다. 실제 시맨틱 캐시(Redis) 값이 아니다.
실행(lab-app-py 폴더): python -I tools/cache_hit_rate.py   (labcore만 쓴다. -I라도 이 파일 위치로 저장소 뿌리를 찾는다)
질문 순서(가짜): 사용자 4명(alice·bob·dave = shop-a, carol = shop-b)이 차례로 공용 FAQ 1개와 개인 질문 1개를 5번씩 묻는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from labcore.cost import ResponseCache  # noqa: E402
from labcore.injection import Intent  # noqa: E402
from labcore.user import UserContext  # noqa: E402


def run(cache, users, q, intent, personal):
    lookups = hits = foreign = 0
    for _ in range(5):
        for u in users:
            lookups += 1
            hit = cache.get(u, q)
            if hit is not None:
                hits += 1
                if personal and not hit.startswith(u.user_id + "님"):
                    foreign += 1
            else:
                answer = f"{u.user_id}님 주문은 배송 중입니다(가짜)" if personal else "배송비는 3,000원입니다(가짜)"
                cache.put(u, q, intent, answer)
    return lookups, hits, foreign


def rate(lookups, hits):
    return f"{hits}/{lookups} ({round(100.0 * hits / lookups)}%)"


def main():
    users = [UserContext.alice(), UserContext.bob(), UserContext.dave(), UserContext.carol()]
    print(f"{'구현':<34} {'공용 FAQ 적중':<16} {'개인 질문 적중':<16} 남의 답을 받은 적중")
    for cache, name in ((ResponseCache.SharedKeyCache(), "수정 전 SharedKeyCache"), (ResponseCache.ScopedCache(), "수정 후 ScopedCache")):
        fl, fh, ff = run(cache, users, "배송비 얼마예요?", Intent.PRODUCT_QA, False)
        ml, mh, mf = run(cache, users, "내 주문 어디까지 왔어?", Intent.ORDER_STATUS, True)
        print(f"{name:<34} {rate(fl, fh):<16} {rate(ml, mh):<16} {ff + mf}")


if __name__ == "__main__":
    main()
