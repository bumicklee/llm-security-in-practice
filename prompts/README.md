# prompts — 수업에서 그대로 복사해 쓰는 프롬프트 (FastAPI·LangChain)

모든 프롬프트는 같은 모양이다: 쓰는 곳 → 목적 → 프롬프트 본문(`{변수}`) → 입력 예 → 기대 출력 예 → 주의. 공격·우회 문구는 어떤 프롬프트에도 없고, 만들게 하지도 않는다. 공격 입력은 `[ATTACK-<범주>-<NN>: 유형 이름]` 자리 표시만 쓴다(`../samples/lab-app-py/attack-registry.yaml`). 대상은 127.0.0.1의 내 랩뿐이다.

예제·소스: https://github.com/bumicklee/llm-security-in-practice.git (이 폴더는 저장소의 `prompts/`). 경로는 저장소 루트(`llm-security-in-practice`) 기준이다. 랩은 `../samples/lab-app-py/`(FastAPI 0.162.0 + LangChain 1.4.7), 평가 키트는 그 안의 `eval-kit/`다.

## 1부 시작하기 · 2부 막기 · 3부 12장 · 1~12장 (앱 코드를 점검·보강)

| 파일 | 종류 | 장 · 절 | 수업 |
| --- | --- | --- | --- |
| [cc-owasp-map.md](cc-owasp-map.md) | Claude Code 점검 | 1장 1.5 | 1-4 |
| [cc-lab-setup-check.md](cc-lab-setup-check.md) | Claude Code 점검 | 2장 2.1·2.5 | 1-6~1-8 |
| [cc-explain-request-json.md](cc-explain-request-json.md) | 분석 | 3장 3.2 | 2-2 |
| [system-prompt-shop-bot.md](system-prompt-shop-bot.md) | 시스템 프롬프트 템플릿 | 3장 3.4~3.5 · 4장 4.1 | 2-1·2-3 |
| [cc-generate-input-guard.md](cc-generate-input-guard.md) | Claude Code 생성 | 4장 4.2~4.3 | 2-4·2-5 |
| [cc-generate-output-schema.md](cc-generate-output-schema.md) | Claude Code 생성 | 4장 4.4 | 2-6 |
| [cc-review-rag-ingestion.md](cc-review-rag-ingestion.md) | Claude Code 점검 | 5장 5.2~5.3 | 3-2·3-3 |
| [rag-document-fence-template.md](rag-document-fence-template.md) | RAG 프롬프트 템플릿 | 5장 5.4~5.5 | 3-3·3-4 |
| [cc-add-tenant-filter.md](cc-add-tenant-filter.md) | Claude Code 생성 | 6장 6.3~6.5 | 3-5~3-7 |
| [cc-estimate-token-cost.md](cc-estimate-token-cost.md) | Claude Code 계산 | 7장 7.2·7.5 | 4-2·4-5 |
| [cc-add-rate-limit-and-budget.md](cc-add-rate-limit-and-budget.md) | Claude Code 생성 | 8장 8.1~8.3 | 4-3·4-4 |
| [cc-audit-tool-authz.md](cc-audit-tool-authz.md) | Claude Code 점검 | 9장 9.2~9.5 · 22장 22.2~22.3 | 5-2~5-4 · 14-1·14-2 |
| [cc-add-ssrf-guard.md](cc-add-ssrf-guard.md) | Claude Code 생성 | 10장 10.1~10.2 | 5-5 |
| [cc-mcp-server-review.md](cc-mcp-server-review.md) | Claude Code 점검 | 10장 10.3~10.4 | 5-6 |
| [cc-review-output-and-logs.md](cc-review-output-and-logs.md) | Claude Code 점검 | 11장 11.1~11.5 | 6-1~6-5 |
| [cc-write-attack-tests.md](cc-write-attack-tests.md) | Claude Code 생성 | 12장 12.2~12.3 · 22장 22.4 | 7-2·7-3 · 14-3 |

## 3부 시험하기 · 4부 출시·운영 · 13~22장 (시험 문제·채점·보고서)

| 파일 | 종류 | 장 · 절 | 수업 |
| --- | --- | --- | --- |
| [cc-threat-map.md](cc-threat-map.md) | Claude Code 분석 | 13장 13.2 · 22장 22.2 | 8-3 · 14-1 |
| [cc-new-target-config.md](cc-new-target-config.md) | Claude Code 생성 | 13장 13.1 · 21장 21.4 · 부록 H | 8-1 · 13-6 |
| [cc-add-benign-cases.md](cc-add-benign-cases.md) | Claude Code 생성 | 14장 14.2~14.3 | 9-1 |
| [cc-add-attack-case-skeleton.md](cc-add-attack-case-skeleton.md) | Claude Code 생성(자리표시 뼈대) | 14~15장 · 22장 22.4 | 9-1~9-7 · 14-3 |
| [judge-rubric-injection.md](judge-rubric-injection.md) | 채점 기준표: 지시 무시·역할 바꾸기 | 14장 14.1·14.3 · 16장 16.4 · 부록 E | 9-1 · 10-3 |
| [judge-rubric-leak.md](judge-rubric-leak.md) | 채점 기준표: 시스템 프롬프트 유출 | 14장 14.5 · 16장 16.4~16.6 · 부록 E | 9-2 · 10-3~10-5 |
| [judge-rubric-overrefusal.md](judge-rubric-overrefusal.md) | 채점 기준표: 정상 질문(과잉 거절) | 14장 14.2~14.3 · 16장 16.4 · 부록 E | 9-1 · 10-3 |
| [judge-rubric-indirect.md](judge-rubric-indirect.md) | 채점 기준표: 간접 인젝션 | 15장 15.1~15.2 · 16장 16.4 · 부록 E | 9-4 · 10-3 |
| [judge-calibration.md](judge-calibration.md) | 불일치 사례로 기준표 고치기 | 16장 16.5~16.6 | 10-4·10-5 |
| [cc-generate-variants.md](cc-generate-variants.md) | 변형 생성 + 사람 검토 체크리스트 | 18장 18.1~18.2 | 11-4 |
| [cc-explain-failure.md](cc-explain-failure.md) | 빨간불 원인 좁히기 | 19장 19.7 · 20장 20.2 | 12-4 |
| [report-summary-lead.md](report-summary-lead.md) | 리드용 3줄 출시 판단 요약 | 20장 20.1·20.4 · 부록 F | 13-1 |
| [report-summary-audience.md](report-summary-audience.md) | 개발·QA·리드별 요약 | 20장 20.4 · 부록 F | 13-1 |
| [review-llm-feature-pr.md](review-llm-feature-pr.md) | PR 리뷰(C01~C20) | 20장 20.5 · 21장 21.5 | 13-3 · 13-7 |
| [cc-incident-to-regression.md](cc-incident-to-regression.md) | 운영 사고 → 회귀 시험 문제 | 21장 21.2 | 13-4 |

- `judge-rubric-*.md`는 사람이 읽는 원본이다. 기계용 사본은 `../samples/lab-app-py/eval-kit/judge/rubrics/*.yaml`이며 **두 곳을 함께 고친다**(version 올림). yaml의 `source:` 칸이 이 파일 이름을 가리킨다.
- `cc-*`는 Claude Code에 붙여 넣는 작업 지시다. 같은 규칙을 스킬로 묶은 것이 `../skills/`의 `llm-security-review`(C01~C20 점검), `llm-attack-tests`(pytest 공격 테스트), `llm-case-writer`(시험 문제 작성), `llm-release-check`(게이트 실행·요약)다.

## 쓰는 법

1. 파일을 열어 "프롬프트 본문" 코드 블록을 복사한다.
2. `{변수}`를 "입력 예" 표의 값(또는 내 프로젝트 값)으로 바꾼다.
3. Claude Code에 붙여 넣는다. 결과는 "기대 출력 예"와 모양이 비슷해야 한다. 기대 출력 예의 숫자는 랩 실측(`../samples/lab-app-py/_실측/`)에서 가져왔고, 파일 이름을 함께 적었다.
4. Claude가 만든 코드는 **랩 정답 코드**(각 파일에 경로 적음)와 비교하고, 랩 폴더에서 `python -m pytest`로 확인한다. 수정 전 상태는 `python -m pytest --lab-target=before`(labcore) 또는 `LAB_PROFILES=before`(앱)로 만든다.
5. 평가 키트 명령은 `eval-kit/` 폴더에서 `python -m evalkit …`로 돌린다(venv를 켠 상태).

## 공통 주의

- Claude가 "방어 있음"이라고 해도 파일:줄을 직접 연다.
- LangChain·FastAPI API 이름이 불확실하면 `# 확인 필요` 주석을 달게 했다. 그 주석이 남은 코드는 공식 문서(부록 C 고정 버전: langchain 1.4.7, langchain-core 1.7.0, fastapi 0.162.0)로 확인하기 전까지 커밋하지 않는다.
- 실서비스 프롬프트·로그 원문을 외부 도구에 붙여 넣지 않는다. `.env`·`eval-kit/private/attack_inputs.yaml`은 열게 하지 않는다.
