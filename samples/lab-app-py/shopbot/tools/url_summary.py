""""이 URL 요약해 줘" 도구(10장).

가져오기는 labcore UrlFetcher(수정 후 = GuardedUrlFetcher: 허용 도메인·내부 주소 차단·리다이렉트마다 재검사).
실제 HTTP는 httpx2를 follow_redirects=False로 쓴다(따라가기는 호출부가 검사 후 직접 한다). 모델에게는 본문 앞 2,000자만.
"""
import httpx2
from langchain.tools import tool
from pydantic import BaseModel, Field

from labcore.ssrf import Page


class Httpx2WebClient:
    """WebClientPort 구현. 리다이렉트를 따라가지 않는다."""

    def __init__(self):
        self._client = httpx2.Client(follow_redirects=False, timeout=httpx2.Timeout(5.0, connect=3.0))

    def get(self, url: str) -> Page:
        try:
            r = self._client.get(url)
            return Page(r.status_code, r.headers.get("location"), r.text)
        except Exception:   # 연결 실패·잘못된 URL 등. 내부 오류 글은 모델에게 보내지 않는다
            return Page(599, None, "fetch error")


class UrlArgs(BaseModel):
    url: str | None = Field(None, description="https URL")


def build_url_tools(lab):
    @tool("summarizeUrl", args_schema=UrlArgs, response_format="content_and_artifact",
          description="허용된 공개 문서 URL의 본문을 가져온다")
    def summarize_url(url=None):
        r = lab.url_fetcher.fetch("null" if url is None else str(url))
        body = r.body_or_reason or ""
        return body[:2000], {"arguments": {"url": "null" if url is None else str(url)},
                             "status": "EXECUTED" if r.ok else "DENIED"}

    return [summarize_url]
