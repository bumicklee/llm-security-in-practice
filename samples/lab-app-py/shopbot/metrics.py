"""관리 앱(127.0.0.1:8082). 비용 메트릭(8장 8.5, 수업 4-7).

GET /healthz  인증 없음 → {"status": "UP"} (평가 키트 health_url, compose 확인)
GET /metrics  HTTP Basic 필요(없으면 401) → prometheus 형식. 카운터 lab_llm_tokens_total{user,kind}(kind = input|output)
레지스트리는 앱마다 따로 만든다(prometheus_client 기본 전역 레지스트리를 쓰면 테스트마다 앱을 새로 만들 때 이름이 겹친다).
"""
import threading

from fastapi import Depends, FastAPI, Response
from prometheus_client import CollectorRegistry, Counter, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from labcore.cost import FakePricing
from shopbot.security import current_user


class LabMetrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.tokens = Counter("lab_llm_tokens", "LLM 토큰 사용량(가짜 LLM이 돌려준 usage)", ["user", "kind"],
                              registry=self.registry)
        self.cost = Counter("lab_llm_cost_krw", "예상 요금(가짜 단가: 입력 10원/1K, 출력 30원/1K)", ["user"],
                            registry=self.registry)

    def record_tokens(self, user_id: str, usage) -> None:
        self.tokens.labels(user_id, "input").inc(usage.prompt_tokens)
        self.tokens.labels(user_id, "output").inc(usage.completion_tokens)
        self.cost.labels(user_id).inc(FakePricing.krw(usage))


def create_mgmt_app(metrics: LabMetrics) -> FastAPI:
    app = FastAPI(title="shop-bot-py management", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz():
        return {"status": "UP"}

    @app.get("/metrics", dependencies=[Depends(current_user)])
    def prom():
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


class MgmtServer:
    """두 번째 uvicorn 서버를 백그라운드 스레드로 띄운다(본 앱의 lifespan에서 시작·종료)."""

    def __init__(self, app: FastAPI, host: str, port: int):
        import uvicorn
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="off"))
        self.thread = threading.Thread(target=self.server.run, daemon=True, name="mgmt-server")

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
