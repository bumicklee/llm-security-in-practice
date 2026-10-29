"""앱 하나의 상태(부품 묶음). create_app()이 테스트마다 새로 만든다.

모듈 전역 싱글턴에 상태(버킷·장부·대화 메모리)를 두면 테스트끼리 섞인다(앞 테스트가 비운 레이트 리밋 버킷이 남는 실패, 12.3).
"""
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request


@dataclass
class LabState:
    settings: Any
    users: Any
    input_guard: Any
    suspicious: Any
    masker: Any
    reply_policy: Any
    audit: Any
    ledger: Any
    limiter: Any
    budget: Any
    orders: Any
    approvals: Any
    coupons: Any
    approval_service: Any
    order_tools: Any
    coupon_tools: Any
    url_fetcher: Any
    scanner: Any
    grounding: Any
    vector_store: Any
    retriever: Any
    rag: Any
    metrics: Any
    model: Any = None
    checkpointer: Any = None
    chat_agent: Any = None
    tools: list = field(default_factory=list)
    pending_reviews: list = field(default_factory=list)
    fixture_ids: list = field(default_factory=list)
    mcp_report: dict | None = None
    agent_builder: Any = None
    _agents: dict = field(default_factory=dict)

    def agent_for(self, model):
        """채팅 모델 하나에 에이전트 하나(모델별로 한 번만 조립). 테스트가 dependency_overrides로 가짜 모델을 넣어도 같은 조립을 탄다."""
        key = id(model)
        if key not in self._agents:
            self._agents[key] = (model, self.agent_builder(model))
        return self._agents[key][1]


def get_lab(request: Request) -> LabState:
    return request.app.state.lab


def get_chat_model(request: Request):
    """채팅 모델 의존성. 테스트는 app.dependency_overrides[get_chat_model] = lambda: 가짜_모델 로 바꾼다(12.3)."""
    return request.app.state.lab.model
