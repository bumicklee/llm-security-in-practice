"""채팅 모델. 가짜 LLM·LM Studio·외부 API 모두 OpenAI 호환 ChatOpenAI 하나로.

- use_responses_api=False 고정: 기본 None이면 설정에 따라 Responses API로 바뀔 수 있다(설계 R4). 가짜 LLM은 Chat Completions만.
- max_retries: openai SDK 3.40.0 DEFAULT_MAX_RETRIES = 2(시도 3번). 랩 수정 후는 1(시도 2번). before 프로필은 SDK 기본값.
- max_tokens=300(8.3). 요청 본문에는 max_completion_tokens로 나간다(langchain-openai 1.7.3 확인). 호환 서버 지원은 서버마다 확인.
"""
from langchain_openai import ChatOpenAI

from shopbot.settings import LabSettings


def build_chat_model(s: LabSettings) -> ChatOpenAI:
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다(external 프로필은 기본값이 없다 = 가짜 키를 밖으로 보내지 않음)")
    if not s.llm_model:
        raise RuntimeError("LLM_MODEL이 없습니다")
    kwargs = dict(model=s.llm_model, base_url=s.llm_base_url, api_key=s.openai_api_key, temperature=s.temperature,
                  max_tokens=s.max_tokens, use_responses_api=False, timeout=60)
    if s.max_retries is not None:
        kwargs["max_retries"] = s.max_retries
    return ChatOpenAI(**kwargs)
