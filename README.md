# LLM 보안 실전 — 예제·소스

「LLM 보안 실전: 프롬프트 인젝션·요금 폭탄·도구 권한을 코드로 막기」 교재와 인프런 강의 「FastAPI LLM 보안 실전」의 실습 저장소입니다.

| 폴더 | 내용 |
| --- | --- |
| [`samples/lab-app-py/`](samples/lab-app-py/README.md) | 실습 랩: 상담봇 shop-bot(FastAPI + LangChain), 방어 코드 `labcore`, 가짜 LLM·요금 대시보드·가짜 MCP, pytest 공격 테스트, 평가 키트(시험 문제 50개), CI 게이트 |
| [`prompts/`](prompts/) | Claude Code에 붙여 쓰는 작업 프롬프트 |
| [`skills/`](skills/README.md) | Claude Code 스킬·훅 |

## 시작하기

```bash
git clone https://github.com/bumicklee/llm-security-in-practice.git
cd llm-security-in-practice/samples/lab-app-py
```

이후 설치는 교재 2장(수업 1-6)을 따릅니다.

## 안전 수칙

- 모든 서버는 내 PC의 `127.0.0.1`에서만 엽니다. 키·사용자·비밀은 모두 가짜 값입니다.
- 공격 입력은 `[ATTACK-INJ-01: 시스템 지시 무시 요청 유형]` 같은 자리표시만 씁니다. 실제 공격 문구는 이 저장소에 없습니다.
