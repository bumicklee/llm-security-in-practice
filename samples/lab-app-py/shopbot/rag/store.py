"""기본 프로필의 벡터 저장소: langchain-core InMemoryVectorStore + 결정적 가짜 임베딩.

- 가짜 임베딩(LabHashEmbedding): 단어를 해시해 64차원 벡터에 더한다(UTF-16 단위 31 곱셈 해시·나머지·L2 정규화).
  실행마다 검색 순서가 같다. 의미 검색 품질은 없다. 권한 필터 확인에는 충분하다.
  DeterministicFakeEmbedding(langchain-core)은 문장마다 난수 벡터라 단어 겹침이 순서에 반영되지 않는다 → 쓰지 않는다.
- LabVectorStore: InMemoryVectorStore의 유사도 계산만 표준 라이브러리로 바꿨다(numpy 없이 돈다, 같은 점수는 넣은 순서).
  filter=는 콜러블(Document → bool)이다. 방법 A의 필터 객체가 이것이다(6장).
- 권한 메타데이터(tenantId·visibility·source·trust)는 "넣을 때" 붙인다(6장 6.3).
"""
import math
import re
import struct

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from labcore.rag import KnowledgeDoc, KnowledgeStore, TrustLevel, Visibility

DIM = 64
_SPLIT = re.compile(r"[\W_]+")


def string_hash31(s: str) -> int:
    """UTF-16 단위로 h = 31*h + c를 32비트 부호 있는 정수로 계산한다(결정적, PYTHONHASHSEED와 무관)."""
    h = 0
    for unit in struct.unpack(f"<{len(s.encode('utf-16-le')) // 2}H", s.encode("utf-16-le")):
        h = (31 * h + unit) & 0xFFFFFFFF
    return h - (1 << 32) if h >= (1 << 31) else h


def _f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


class LabHashEmbedding(Embeddings):
    def _vector(self, text: str) -> list[float]:
        v = [0.0] * DIM
        for w in _SPLIT.split(text.lower()):
            if len(w.encode("utf-16-le")) // 2 < 2:
                continue
            v[string_hash31(w) % DIM] += 1.0
        n = math.sqrt(sum(x * x for x in v))
        return [_f32(x / n) for x in v] if n > 0 else v

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _cosine(a, b) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return 0.0 if na == 0 or nb == 0 else sum(x * y for x, y in zip(a, b)) / (na * nb)


class LabVectorStore(InMemoryVectorStore):
    def _similarity_search_with_score_by_vector(self, embedding, k=4, filter=None):   # noqa: A002
        rows = []
        for d in self.store.values():
            doc = Document(id=d["id"], page_content=d["text"], metadata=d["metadata"])
            if filter is None or filter(doc):
                rows.append((doc, _cosine(embedding, d["vector"]), d["vector"]))
        rows.sort(key=lambda r: -r[1])   # 안정 정렬: 같은 점수는 넣은 순서
        return rows[:k]


def to_document(d: KnowledgeDoc) -> Document:
    return Document(id=d.id, page_content=d.text, metadata={
        "tenantId": d.tenant_id, "visibility": d.visibility.value, "source": d.source, "trust": d.trust.value})


def to_knowledge_doc(doc: Document) -> KnowledgeDoc:
    m = doc.metadata
    return KnowledgeDoc(doc.id, str(m.get("tenantId")), Visibility(m.get("visibility", "PUBLIC")),
                        str(m.get("source", "unknown")), TrustLevel(m.get("trust", "CUSTOMER")), doc.page_content)


def build_memory_store() -> LabVectorStore:
    store = LabVectorStore(LabHashEmbedding())
    store.add_documents([to_document(d) for d in KnowledgeStore.seed_docs()])
    return store
