"""쇼핑몰 상담봇(FastAPI + LangChain) 랩 앱. labcore 부품을 의존성·미들웨어·도구로 연결만 한다.

실행: uvicorn shopbot.main:app --host 127.0.0.1 --port 8080          (가짜 LLM 127.0.0.1:8070 필요: python -I tools/fake_llm.py)
      LAB_PROFILES=before uvicorn shopbot.main:app --host 127.0.0.1 --port 8080   (수정 전)
      LAB_PROFILES=eval / before,eval                                            (평가 키트 연결)
create_app(settings)은 부르는 때마다 새 상태(버킷·장부·메모리)를 만든다. 테스트는 테스트마다 새 앱을 만든다(12.3).
같은 프로세스에서 관리 앱(127.0.0.1:8082 /healthz·/metrics)과 가짜 관리 페이지(127.0.0.1:8081, SSRF 실습 대상)도 띄운다.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from langchain_core.globals import get_debug

from labcore.audit import AuditLog
from labcore.cost import TokenBudget, UsageLedger, UserRateLimiter
from labcore.injection import InputGuard, LeakDetector, ReplyPolicy, SuspiciousInputLog
from labcore.output import PiiMasker
from labcore.rag import GroundingPolicy, IngestionScanner
from labcore.ssrf import GuardedUrlFetcher, NaiveUrlFetcher, UrlFetchGuard, system_resolver
from labcore.tools import (ApprovalQueue, ApprovalService, AuthorizedCouponTools, AuthorizedOrderTools, CouponLedger,
                           OrderRepository, TrustingCouponTools, TrustingOrderTools)
from shopbot.agent.factory import build_chat_agent, build_checkpointer
from shopbot.agent.middleware import TokenMeter
from shopbot.agent.model import build_chat_model
from shopbot.metrics import LabMetrics, MgmtServer, create_mgmt_app
from shopbot.rag.tenant_retriever import TenantScopedRetriever
from shopbot.security import LAB_USERS
from shopbot.settings import LabSettings, load_settings
from shopbot.state import LabState
from shopbot.tools.coupons import build_coupon_tools
from shopbot.tools.orders import build_order_tools
from shopbot.tools.registry_check import verify_tool_allowlist
from shopbot.tools.url_summary import Httpx2WebClient, build_url_tools
from shopbot.web import approvals, chat, lab as lab_api, product_qa
from shopbot.web.errors import (BudgetExceeded, InputRejected, budget_exceeded_handler, input_rejected_handler,
                                internal_error_handler)
from shopbot.web.rate_limit import LimitsRedisLimiter, RateLimited
from shopbot.web.request_id import RequestIdMiddleware

log = logging.getLogger("shopbot")
STATIC = Path(__file__).resolve().parent / "static"
# 프롬프트 원문을 밖(트레이싱 SaaS)으로 보내는 스위치(11.5). 이름은 langsmith 0.14.14 utils.tracing_is_enabled 소스로 확인
TRACING_ENV = ("LANGSMITH_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING")


class PromptLoggingRefused(RuntimeError):
    pass


def check_prompt_logging(s: LabSettings, env=os.environ) -> list[str]:
    """트레이싱 환경 변수·set_debug(True)가 켜져 있으면 경고하고, 기본·eval 프로필에서는 시작을 거부한다(fail closed)."""
    on = [k for k in TRACING_ENV if str(env.get(k, "")).strip().lower() == "true"]
    if get_debug():
        on.append("langchain_core.globals.set_debug(True)")
    if not on:
        return []
    msg = f"프롬프트 원문이 밖으로 나갈 수 있는 설정이 켜져 있습니다: {on}"
    if not s.profiles or "eval" in s.profiles:   # 기본(수정 후)·eval 프로필
        raise PromptLoggingRefused(msg + " → 기본·eval 프로필에서는 시작하지 않습니다(11.5)")
    log.warning(msg)
    return on


def build_state(s: LabSettings) -> LabState:
    d = s.defense
    audit_log = logging.getLogger("shopbot.audit")
    audit = AuditLog(sink=lambda line: audit_log.info(line))   # 감사 로그 = JSON 한 줄(11장)
    ledger = UsageLedger()
    if s.rate_limit_store == "redis":
        limiter = LimitsRedisLimiter(s.redis_url, s.rate_limit_per_minute)
    else:
        limiter = UserRateLimiter.lab_defaults() if s.rate_limit_per_minute == 10 else UserRateLimiter(s.rate_limit_per_minute, 60)
    orders, approvals_q, coupons = OrderRepository.seeded(), ApprovalQueue(), CouponLedger()
    web = Httpx2WebClient()
    url_fetcher = (GuardedUrlFetcher(UrlFetchGuard(s.fetch_allowed_hosts, {"https"}, system_resolver), web)
                   if d.ssrf_guard else NaiveUrlFetcher(web))
    if s.vector_store == "redis":
        from shopbot.rag.redis_store import build_redis_store
        store = build_redis_store(s.redis_url)
    else:
        from shopbot.rag.store import build_memory_store
        store = build_memory_store()
    masker = PiiMasker()
    lab = LabState(
        settings=s, users=LAB_USERS, input_guard=InputGuard(), suspicious=SuspiciousInputLog(), masker=masker,
        reply_policy=ReplyPolicy(LeakDetector()), audit=audit, ledger=ledger, limiter=limiter,
        budget=TokenBudget(TokenBudget.Limits.lab_defaults(), ledger), orders=orders, approvals=approvals_q, coupons=coupons,
        approval_service=ApprovalService(orders, approvals_q, audit, coupons),
        order_tools=AuthorizedOrderTools(orders, approvals_q, audit) if d.tool_authz else TrustingOrderTools(orders),
        coupon_tools=(AuthorizedCouponTools(orders, approvals_q, coupons, audit) if d.tool_authz
                      else TrustingCouponTools(orders, coupons)),
        url_fetcher=url_fetcher, scanner=IngestionScanner(s.link_allowed_hosts),
        grounding=GroundingPolicy(s.link_allowed_hosts), vector_store=store, retriever=None, rag=None,
        metrics=LabMetrics())
    return lab


def create_app(settings: LabSettings | None = None, chat_model=None) -> FastAPI:
    """chat_model: 테스트가 넣는 가짜 채팅 모델(키·네트워크 없이). 없으면 ChatOpenAI(가짜 LLM 8070)."""
    s = settings or load_settings()
    check_prompt_logging(s)
    lab = build_state(s)
    lab.model = chat_model if chat_model is not None else build_chat_model(s)
    lab.checkpointer = build_checkpointer()
    meter = TokenMeter(lab.budget, lab.ledger, s.defense.token_budget, lab.metrics)
    lab.tools = build_order_tools(lab) + build_coupon_tools(lab) + build_url_tools(lab)
    verify_tool_allowlist(lab.tools, s.tools_allowlist_exclude)   # 목록 밖 도구가 있으면 앱이 뜨지 않는다(9.5)
    lab.agent_builder = lambda model: build_chat_agent(lab, model, lab.tools, meter)
    lab.chat_agent = lab.agent_for(lab.model)
    lab.rag = TenantScopedRetriever(lab.vector_store, s, lab.grounding, lab.model, meter, lab.masker)
    lab.retriever = lab.rag

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        side = []
        if s.mcp_enabled:   # 관리 앱(healthz)보다 먼저: healthz가 200이면 [mcp] 로그도 이미 찍혀 있다(10장 10.3)
            from shopbot.mcp.gate import report_mcp_tools
            lab.mcp_report = await report_mcp_tools(s.mcp_url, s.mcp_allowed_tools)
        if s.side_servers:
            mgmt = MgmtServer(create_mgmt_app(lab.metrics), s.mgmt_host, s.mgmt_port)
            mgmt.start()
            side.append(mgmt)
            if s.admin_page_enabled:
                from shopbot.admin.fake_admin_page import FakeAdminPage
                page = FakeAdminPage(s.admin_page_port)
                page.start()
                side.append(page)
        log.info("shop-bot-py 시작 · 프로필 %s · 방어 스위치 %s", ",".join(s.profiles) or "default",
                 {k: v for k, v in s.defense.model_dump().items()})
        yield
        for x in reversed(side):
            x.stop()

    app = FastAPI(title="shop-bot-py", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.lab = lab
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(InputRejected, input_rejected_handler)
    app.add_exception_handler(BudgetExceeded, budget_exceeded_handler)

    @app.exception_handler(RateLimited)
    async def rate_limited_handler(request: Request, e: RateLimited):
        return JSONResponse(status_code=429, content=e.detail, headers=e.headers)

    app.add_exception_handler(Exception, internal_error_handler)

    for name in ("index.html", "app.js"):
        def make(fname):
            return lambda: FileResponse(STATIC / fname)
        app.add_api_route("/" + name, make(name), methods=["GET"], include_in_schema=False)
    app.add_api_route("/", lambda: FileResponse(STATIC / "index.html"), methods=["GET"], include_in_schema=False)

    app.include_router(chat.build_router(s.eval_enabled))
    app.include_router(product_qa.router)
    app.include_router(approvals.router)
    app.include_router(lab_api.router)
    if s.eval_enabled:   # eval 프로필일 때만
        from shopbot.eval.router import router as eval_router
        app.include_router(eval_router)
    return app


def _configure_logging():
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)


class _LazyApp:
    """uvicorn shopbot.main:app — 처음 요청(또는 lifespan)이 올 때 설정을 읽어 앱을 만든다. import만으로 포트를 열지 않는다."""

    def __init__(self):
        self._app = None

    async def __call__(self, scope, receive, send):
        if self._app is None:
            _configure_logging()
            try:
                self._app = create_app()
            except Exception as e:   # 시작 검사(트레이싱 fail closed·도구 허용 목록 등)에 걸리면 uvicorn이 확실히 멈추게
                log.error("시작 거부: %s: %s", type(e).__name__, e)
                if scope["type"] == "lifespan":
                    await receive()   # lifespan.startup
                    await send({"type": "lifespan.startup.failed", "message": f"{type(e).__name__}: {e}"})
                    return
                raise
        await self._app(scope, receive, send)


app = _LazyApp()
