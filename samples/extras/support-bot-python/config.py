"""가나다몰 상담 챗봇 설정 읽기.

목적: .env 파일과 환경 변수에서 설정을 읽는다(외부 패키지 없이).
대응 장: 2장(2.1 실습 앱 띄우기, 2.2 모델 주소 바꿔 끼우기)
실행: 직접 실행하지 않는다. app.py가 가져다 쓴다.
"""
import hashlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PROMPT_FILES = {
    "v1": "system_v1.txt",
    "v2": "system_v2.txt",
    "v3": "system_v3_strict.txt",
    "v4": "system_v4.txt",
}

DEFAULTS = {
    "BOT_HOST": "127.0.0.1",
    "BOT_PORT": "8000",
    "BOT_MODE": "stub",
    "BOT_PROFILE": "v1",
    "LLM_BASE_URL": "http://127.0.0.1:1234/v1",
    "LLM_MODEL": "local-model",
    "LLM_API_KEY": "lm-studio-FAKE-KEY",
    "LLM_TEMPERATURE": "0.7",
    "APP_AUTHZ": "on",
    "EXPOSE_TRACE": "1",
    "ADMIN_ENDPOINTS": "1",
    "STUB_SEED": "42",
    "FIXTURES_DIR": "docs/fixtures-injected",
    "BOT_ACCESS_LOG": "1",
    "SYSTEM_PROMPT_FILE": "",
}

# 서버를 묶는 주소는 127.0.0.1 하나만 허용한다("localhost"는 hosts 설정에 따라 다른 주소로 풀릴 수 있다)
ALLOWED_HOSTS = {"127.0.0.1"}


def _read_dotenv(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Settings:
    def __init__(self, overrides=None):
        merged = dict(DEFAULTS)
        merged.update(_read_dotenv(BASE_DIR / ".env"))
        for key in DEFAULTS:
            if key in os.environ:
                merged[key] = os.environ[key]
        if overrides:
            merged.update({k: str(v) for k, v in overrides.items()})
        self.raw = merged

        self.host = merged["BOT_HOST"]
        if self.host not in ALLOWED_HOSTS:
            raise SystemExit(
                f"BOT_HOST={self.host} 는 허용하지 않습니다. 실습 앱은 127.0.0.1에만 묶습니다."
            )
        self.port = int(merged["BOT_PORT"])
        self.mode = merged["BOT_MODE"]
        if self.mode not in ("stub", "openai"):
            raise SystemExit("BOT_MODE는 stub 또는 openai 입니다.")
        self.profile = merged["BOT_PROFILE"]
        if self.profile not in PROMPT_FILES:
            raise SystemExit("BOT_PROFILE은 v1, v2, v3, v4 중 하나입니다.")
        self.llm_base_url = merged["LLM_BASE_URL"].rstrip("/")
        self.llm_model = merged["LLM_MODEL"]
        self.llm_api_key = merged["LLM_API_KEY"]
        self.llm_temperature = float(merged["LLM_TEMPERATURE"])
        self.app_authz = merged["APP_AUTHZ"].lower() in ("on", "1", "true", "yes")
        self.expose_trace = merged["EXPOSE_TRACE"] == "1"
        self.admin_endpoints = merged["ADMIN_ENDPOINTS"] == "1"
        self.stub_seed = merged["STUB_SEED"]
        self.access_log = merged["BOT_ACCESS_LOG"] == "1"
        fixtures = Path(merged["FIXTURES_DIR"])
        self.fixtures_dir = fixtures if fixtures.is_absolute() else BASE_DIR / fixtures

    @property
    def prompt_version(self):
        # 프로필 + 프롬프트 내용 해시 6자리: 한 글자만 바뀌어도 보고서에서 구분된다(10.5)
        digest = hashlib.sha256(self.system_prompt().encode("utf-8")).hexdigest()[:6]
        return f"{self.profile}@{digest}"

    def system_prompt(self):
        override = self.raw.get("SYSTEM_PROMPT_FILE")
        path = Path(override) if override else BASE_DIR / "prompts" / PROMPT_FILES[self.profile]
        lines = path.read_text(encoding="utf-8").splitlines()
        # '#'으로 시작하는 줄은 작성자 메모 → 모델에 보내지 않는다
        return "\n".join(l for l in lines if not l.lstrip().startswith("#")).strip() + "\n"

    def public_summary(self):
        return {
            "mode": self.mode,
            "profile": self.profile,
            "prompt_version": self.prompt_version,
            "model": self.llm_model if self.mode == "openai" else "stub",
            "app_authz": self.app_authz,
            "temperature": self.llm_temperature if self.mode == "openai" else None,
        }
