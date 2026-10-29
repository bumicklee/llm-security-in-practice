"""설정: 프로필 YAML 합치기 + 방어 스위치 11개.

LAB_PROFILES=before,eval 처럼 쉼표로 고른다. 순서: default.yaml → 고른 프로필(왼쪽부터) → 환경 변수.
기본(아무것도 안 고름 또는 default) = 수정 후. 스위치 하나만 바꾸기: LAB_DEFENSE_OFF=a,b / LAB_DEFENSE_ON=a,b. 스위치 이름은 snake_case, HTTP(/api/lab/flags)에는 camelCase로 낸다(HTTP 계약).
"""
import os
from pathlib import Path
from typing import Literal, Any

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings, SettingsConfigDict

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"
KNOWN_PROFILES = {"default", "before", "eval", "lmstudio", "external", "redis", "mcp"}


class Defense(BaseModel):
    """방어 스위치 11개. 기본은 모두 켬(수정 후). before 프로필은 모두 끈다."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)
    secret_free_prompt: bool = True   # 4장 4.1
    input_guard: bool = True          # 4장 4.2~4.3
    output_schema: bool = True        # 4장 4.4
    rag_guard: bool = True            # 5장
    tenant_filter: bool = True        # 6장
    rate_limit: bool = True           # 8장 8.1
    token_budget: bool = True         # 8장 8.2
    tool_authz: bool = True           # 9장
    ssrf_guard: bool = True           # 10장
    output_escape: bool = True        # 11장 11.1
    pii_mask: bool = True             # 11장 11.2


class LabSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", frozen=True)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # 환경 변수는 load_settings()가 정해진 이름(ENV_OVERRIDES·LAB_DEFENSE_*)만 읽는다. 아무 환경 변수나 설정을 바꾸지 못하게
        return (init_settings,)

    active_profiles: tuple[str, ...] = ()
    llm_base_url: str = "http://127.0.0.1:8070/v1"
    openai_api_key: str | None = "sk-test-FAKE-0000"
    llm_model: str | None = "fake-shop-model"
    max_retries: int | None = 1
    max_tokens: int = 300
    temperature: float = 0.0
    memory_max_messages: int = 20
    tool_calls_total: int = 5
    tool_calls_per_tool: int = 3
    model_calls_per_run: int = 8
    # 출력 스키마를 받는 방식(4장 4.4·2장 2.4). provider = 서버에 response_format(json_schema)을 함께 보냄.
    # tool = 최종 답을 "답 제출" 도구 호출로 받음(LM Studio 같은 로컬 서버는 도구와 response_format을 함께 처리하지 못한다)
    structured_output: Literal["provider", "tool"] = "provider"
    rate_limit_per_minute: int = 10
    rate_limit_store: str = "memory"
    vector_store: str = "memory"
    redis_url: str = "redis://127.0.0.1:6379/0"
    fetch_allowed_hosts: tuple[str, ...] = ("docs.shop.example",)
    link_allowed_hosts: tuple[str, ...] = ("shop-a.example",)
    admin_page_enabled: bool = True
    admin_page_port: int = 8081
    mgmt_host: str = "127.0.0.1"
    mgmt_port: int = 8082
    eval_enabled: bool = False
    mcp_enabled: bool = False
    mcp_url: str = "http://127.0.0.1:8095/mcp"
    mcp_allowed_tools: tuple[str, ...] = ("search_products",)
    tools_allowlist_exclude: tuple[str, ...] = ()
    side_servers: bool = True       # 관리 앱(8082)·가짜 관리 페이지(8081)를 같이 띄울지. 테스트는 False
    defense: Defense = Defense()

    @property
    def profiles(self) -> tuple[str, ...]:
        return self.active_profiles

    @property
    def is_before(self) -> bool:
        return "before" in self.active_profiles


# 환경 변수 → 설정 키(프로필보다 이긴다). compose·외부 API·포트 바꾸기용
ENV_OVERRIDES = {"LLM_BASE_URL": "llm_base_url", "OPENAI_API_KEY": "openai_api_key", "LLM_MODEL": "llm_model",
                 "HOST": "mgmt_host", "MGMT_PORT": "mgmt_port", "REDIS_URL": "redis_url", "MCP_URL": "mcp_url",
                 "LAB_TOOLS_ALLOWLIST_EXCLUDE": "tools_allowlist_exclude"}


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def parse_profiles(value: str | None) -> tuple[str, ...]:
    names = tuple(p.strip() for p in (value or "").split(",") if p.strip() and p.strip() != "default")
    unknown = [p for p in names if p not in KNOWN_PROFILES]
    if unknown:
        raise ValueError(f"알 수 없는 프로필: {unknown} (가능: {sorted(KNOWN_PROFILES)})")
    return names


def load_settings(profiles: str | list[str] | None = None, env: dict | None = None, **overrides: Any) -> LabSettings:
    """profiles가 None이면 환경 변수 LAB_PROFILES를 읽는다. overrides는 테스트·시연용(가장 마지막에 이긴다)."""
    env = os.environ if env is None else env
    names = parse_profiles(env.get("LAB_PROFILES") if profiles is None else
                           profiles if isinstance(profiles, str) else ",".join(profiles))
    data: dict = yaml.safe_load((PROFILE_DIR / "default.yaml").read_text(encoding="utf-8")) or {}
    for name in names:
        data = _merge(data, yaml.safe_load((PROFILE_DIR / f"{name}.yaml").read_text(encoding="utf-8")) or {})
    for var, key in ENV_OVERRIDES.items():
        if env.get(var):
            data[key] = [x.strip() for x in env[var].split(",") if x.strip()] if key == "tools_allowlist_exclude" \
                else env[var]
    # 방어를 하나씩 켜고 끄기(장마다 전후 비교): LAB_DEFENSE_OFF=secret_free_prompt,output_schema
    for var, value in (("LAB_DEFENSE_OFF", False), ("LAB_DEFENSE_ON", True)):
        for name in [x.strip() for x in (env.get(var) or "").split(",") if x.strip()]:
            if name not in Defense.model_fields:
                raise ValueError(f"{var}: 알 수 없는 방어 스위치 {name!r} (가능: {list(Defense.model_fields)})")
            data.setdefault("defense", {})[name] = value
    data = _merge(data, overrides)
    data["active_profiles"] = names
    return LabSettings(**data)
