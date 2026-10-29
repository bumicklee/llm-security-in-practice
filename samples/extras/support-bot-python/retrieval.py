"""아주 작은 FAQ 검색기(키워드 겹침 점수).

목적: '챗봇이 읽는 문서'를 재현한다. 시험용 문서(fixtures)는 켰을 때만 색인에 들어간다.
대응 장: 6장(6.2 검색 문서에 시험용 지시 넣기 — 넣었다 빼는 장치)
"""
import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "docs" / "faq"
TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")


def _tokens(text):
    out = set()
    for tok in TOKEN.findall(text.lower()):
        out.add(tok)
        # 한국어 조사 때문에 놓치지 않도록 앞 2글자도 넣는다(아주 단순한 방식)
        if len(tok) >= 2 and re.match(r"[가-힣]", tok):
            out.add(tok[:2])
    return out


class Retriever:
    def __init__(self, fixtures_dir):
        self.fixtures_dir = Path(fixtures_dir)
        self.fixtures_enabled = False
        self.base_docs = self._load(DOCS_DIR)

    @staticmethod
    def _load(folder):
        docs = []
        if not folder.exists():
            return docs
        for path in sorted(folder.glob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            text = path.read_text(encoding="utf-8")
            docs.append({"name": path.name, "text": text, "tokens": _tokens(text)})
        return docs

    def set_fixtures(self, enabled):
        self.fixtures_enabled = bool(enabled)

    def search(self, query, k=2):
        docs = list(self.base_docs)
        if self.fixtures_enabled:
            docs += [dict(d, fixture=True) for d in self._load(self.fixtures_dir)]
        q = _tokens(query)
        scored = []
        for d in docs:
            score = len(q & d["tokens"])
            if score:
                # 시험용 문서는 같은 점수면 앞에 온다(시험이 확실히 닿도록)
                scored.append((score + (0.5 if d.get("fixture") else 0), d))
        scored.sort(key=lambda x: -x[0])
        return [d for _, d in scored[:k]]
