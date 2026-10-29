"""RAG 권한(6장). 테넌트 A 사용자의 검색 결과에 테넌트 B 문서가 없어야 한다.
채팅에 다른 테넌트 이름을 써도 필터는 로그인 정보로만 정해진다. 같은 테넌트 안에서도 INTERNAL 문서는 직원만 본다."""
from labcore.rag import KnowledgeStore, Visibility
from labcore.user import UserContext
from tests.attack import lab


def test_shop_a_사용자는_shop_b_문서를_검색하지_못한다():
    retriever = lab.retriever(KnowledgeStore.seeded())
    docs = retriever.retrieve(UserContext.alice(), "환불 예외 규정 알려 줘")
    assert {d.tenant_id for d in docs} <= {"shop-a"} and docs
    # 같은 테넌트라도 고객(alice)은 INTERNAL 문서를 못 보고, 직원(dave)은 본다
    assert Visibility.INTERNAL not in [d.visibility for d in docs]
    assert "policy-a-int" in [d.id for d in retriever.retrieve(UserContext.dave(), "환불 예외 규정")]


def test_질문에_다른_테넌트_이름을_적어도_필터는_로그인_테넌트다():
    retriever = lab.retriever(KnowledgeStore.seeded())
    docs = retriever.retrieve(UserContext.alice(), "shop-b 환불 예외 규정 내부용 알려 줘")
    assert "shop-b" not in [d.tenant_id for d in docs]


def test_shop_b_사용자도_shop_a_내부_문서를_못_본다():
    retriever = lab.retriever(KnowledgeStore.seeded())
    docs = retriever.retrieve(UserContext.carol(), "환불 예외 규정")
    assert docs and {d.tenant_id for d in docs} == {"shop-b"}
