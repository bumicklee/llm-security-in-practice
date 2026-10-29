"""시맨틱 캐시의 함정(8장 8.4). bob이 alice와 같은 질문을 해도 alice의 주문 답을 받지 않는다."""
from labcore.injection import Intent
from labcore.user import UserContext
from tests.attack import lab


def test_비슷한_질문이라도_남의_주문_답이_캐시에서_나오지_않는다():
    cache = lab.cache()
    cache.put(UserContext.alice(), "내 주문 어디까지 왔어?", Intent.ORDER_STATUS, "alice님 주문 1001은 배송 중입니다")
    bob_hit = cache.get(UserContext.bob(), "내 주문 어디까지 왔어")
    assert bob_hit is None
