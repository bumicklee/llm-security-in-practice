"""redis 프로필의 벡터 저장소(Redis 8 검색·벡터, compose의 vector-db = redis:8.10.3).

필터에 쓸 메타데이터 필드(tenantId·visibility·trust·source)를 TAG로 미리 선언한다(FT.CREATE). 선언하지 않은 필드로는 거를 수 없다.
방법 B(6장): 필터는 Redis 검색 질의 "문자열"(@tenantId:{shop\\-a})이다. 문자열에 값을 이어 붙이므로
  ① 로그인 정보의 값이라도 형식 검사(FilterValues.require_safe_tenant) ② 태그 값 이스케이프(escape_tag)를 둘 다 한다.
방법 A와 섞지 않는다: 같은 서비스 안에서 필터를 만드는 길은 하나로 둔다.
"""
import re
import struct

from langchain_core.documents import Document

from labcore.rag import FilterValues, KnowledgeStore
from shopbot.rag.store import DIM, LabHashEmbedding, to_document

INDEX = "shop-docs"
PREFIX = "doc:"
_TAG_SPECIAL = re.compile(r"([,.<>{}\[\]\"':;!@#$%^&*()\-+=~|/\\ ])")


def escape_tag(value: str) -> str:
    """Redis 검색 TAG 값의 특수 문자를 역슬래시로 이스케이프한다(shop-a → shop\\-a)."""
    return _TAG_SPECIAL.sub(r"\\\1", value)


def tenant_query(user, staff_sees_internal: bool = True) -> str:
    tenant = escape_tag(FilterValues.require_safe_tenant(user.tenant_id))
    q = f"@tenantId:{{{tenant}}}"
    if not (user.staff and staff_sees_internal):
        q += " @visibility:{PUBLIC}"
    return q


class RedisLabVectorStore:
    """InMemoryVectorStore와 같은 몇 가지 메서드만(add_documents·delete·similarity_search)."""

    def __init__(self, redis_url: str):
        import redis
        self.r = redis.Redis.from_url(redis_url)
        self.emb = LabHashEmbedding()
        self._ensure_index()

    def _ensure_index(self):
        from redis.commands.search.field import TagField, TextField, VectorField
        from redis.commands.search.index_definition import IndexDefinition, IndexType
        try:
            self.r.ft(INDEX).dropindex(delete_documents=True)
        except Exception:
            pass
        self.r.ft(INDEX).create_index(
            [TextField("text"), TagField("tenantId"), TagField("visibility"), TagField("trust"), TagField("source"),
             VectorField("vector", "FLAT", {"TYPE": "FLOAT32", "DIM": DIM, "DISTANCE_METRIC": "COSINE"})],
            definition=IndexDefinition(prefix=[PREFIX], index_type=IndexType.HASH))

    def add_documents(self, docs: list[Document]) -> list[str]:
        for d in docs:
            vec = struct.pack(f"<{DIM}f", *self.emb.embed_query(d.page_content))
            self.r.hset(PREFIX + d.id, mapping={"text": d.page_content, "vector": vec, **d.metadata})
        return [d.id for d in docs]

    def delete(self, ids: list[str]) -> None:
        if ids:
            self.r.delete(*[PREFIX + i for i in ids])

    def similarity_search(self, query: str, k: int = 4, filter: str | None = None) -> list[Document]:   # noqa: A002
        from redis.commands.search.query import Query
        base = f"({filter})" if filter else "*"
        q = Query(f"{base}=>[KNN {k} @vector $v AS score]").sort_by("score").return_fields(
            "text", "tenantId", "visibility", "trust", "source", "score").dialect(2)
        vec = struct.pack(f"<{DIM}f", *self.emb.embed_query(query))
        res = self.r.ft(INDEX).search(q, query_params={"v": vec})
        return [Document(id=doc.id[len(PREFIX):], page_content=doc.text,
                         metadata={"tenantId": doc.tenantId, "visibility": doc.visibility, "trust": doc.trust,
                                   "source": doc.source}) for doc in res.docs]

    def get_by_ids(self, ids):
        return []


def build_redis_store(redis_url: str) -> RedisLabVectorStore:
    store = RedisLabVectorStore(redis_url)
    store.add_documents([to_document(d) for d in KnowledgeStore.seed_docs()])
    return store
