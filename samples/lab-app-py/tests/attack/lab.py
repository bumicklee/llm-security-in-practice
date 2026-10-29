"""공격 테스트가 쓰는 조립기. --lab-target=before 이면 수정 전 구현, 아니면 수정 후 구현을 준다.

테스트 본문은 두 경우 모두 같다: "공격이 막혀야 한다"는 계약만 적는다.
"""
from labcore import target
from labcore.audit import AuditLog
from labcore.cost import (InputGuard, LimitedGateway, OpenGateway, ResponseCache, TokenBudget, UsageLedger,
                          UserRateLimiter)
from labcore.injection import GuardedSupportBot, NaiveSupportBot
from labcore.output import ReplyRenderer
from labcore.rag import (GroundingPolicy, GuardedRagAnswerer, IngestionScanner, KnowledgeStore, NaiveRagAnswerer,
                         TenantScopedRetriever, UnfilteredRetriever)
from labcore.ssrf import GuardedUrlFetcher, NaiveUrlFetcher, UrlFetchGuard
from labcore.tools import ApprovalQueue, AuthorizedOrderTools, OrderRepository, TrustingOrderTools

LINK_HOSTS = {"shop-a.example"}
FETCH_HOSTS = {"docs.shop.example", "rebind.shop.example"}


def before() -> bool:
    return target.is_before()


def support_bot(llm):
    return NaiveSupportBot(llm) if before() else GuardedSupportBot.with_defaults(llm)


def rag_answerer(store: KnowledgeStore, llm):
    if before():
        return NaiveRagAnswerer(store, llm)
    return GuardedRagAnswerer(store, llm, IngestionScanner(LINK_HOSTS), GroundingPolicy(LINK_HOSTS))


def retriever(store: KnowledgeStore):
    return UnfilteredRetriever(store) if before() else TenantScopedRetriever(store)


def gateway(llm, ledger: UsageLedger):
    """시간이 멈춘 레이트 리미터(테스트 중 버킷이 다시 차지 않게)."""
    if before():
        return OpenGateway(llm, ledger)
    return LimitedGateway(llm, ledger, UserRateLimiter(10, 60, clock_ns=lambda: 0),
                          TokenBudget(TokenBudget.Limits.lab_defaults(), ledger), InputGuard(), 20, 200)


def cache():
    return ResponseCache.SharedKeyCache() if before() else ResponseCache.ScopedCache()


def order_tools(repo: OrderRepository, q: ApprovalQueue, audit: AuditLog):
    return TrustingOrderTools(repo) if before() else AuthorizedOrderTools(repo, q, audit)


def url_fetcher(web, resolver):
    if before():
        return NaiveUrlFetcher(web)
    return GuardedUrlFetcher(UrlFetchGuard(FETCH_HOSTS, {"https"}, resolver), web)


def renderer() -> ReplyRenderer:
    return ReplyRenderer.RAW if before() else ReplyRenderer.ESCAPED
