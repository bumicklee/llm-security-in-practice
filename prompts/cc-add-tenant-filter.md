# 프롬프트: 벡터 검색에 테넌트 필터 강제하기

- **쓰는 곳:** 6장 6.3~6.5, 수업 3-5~3-7
- **도구:** Claude Code
- **목적:** 모든 검색이 한 곳을 지나고, 필터 값은 로그인 정보에서만 오도록 바꾼다. 테넌트 격리 pytest도 만든다.

## 프롬프트 본문

```text
이 프로젝트의 벡터 검색 경로를 고쳐라.

1. similarity_search·as_retriever·invoke(검색기)·직접 만든 검색 함수를 부르는 곳을 모두 찾아 목록으로 먼저 보여 줘.
2. 검색 진입점을 {진입점} 하나로 모은다. 라우터·도구·다른 서비스는 벡터 저장소 객체를 직접 쓰지 않게 한다.
3. 필터:
   - 값은 {사용자_정보} (FastAPI 로그인 의존성이 만든 사용자)에서만 가져온다. 요청 본문·채팅 내용·모델 인자에서 가져오지 않는다.
   - 방법 A(기본): 서버가 사용자 정보로 만든 콜러블 필터 filter=lambda doc: doc.metadata["tenantId"] == tenant ... (InMemoryVectorStore)
   - 방법 B(Redis 등 질의 문자열을 받는 저장소): 값은 정규식 {테넌트_형식} 검사를 통과한 것만, 태그 특수 문자는 이스케이프.
     문자열을 f-string·+ 로 이어 붙인 필터는 SQL 문자열 이어 붙이기와 같은 위험이라고 주석을 단다.
   - 직원은 같은 테넌트의 INTERNAL 문서까지, 고객은 PUBLIC만.
4. pytest {테스트_파일}: 테넌트 A 사용자로 B 문서가 안 나온다, 질문에 B 이름을 적어도 안 나온다, B 사용자도 A 내부 문서를 못 본다.
   같은 테스트를 수정 전 구현(필터 없음)에 돌리면 빨강이어야 한다.
5. 바뀐 부분만 diff로. 저장소 API 이름이 확실하지 않으면 # 확인 필요.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{진입점}` | `TenantScopedRetriever.search(user, question)` (`shopbot/rag/tenant_retriever.py`) |
| `{사용자_정보}` | `UserContext.tenant_id`·`.staff` (`shopbot/security.py`의 `current_user`) |
| `{테넌트_형식}` | `[a-z0-9-]{1,32}` (`labcore/rag`의 `FilterValues.require_safe_tenant`) |
| `{테스트_파일}` | `tests/attack/test_tenant_isolation.py` |

## 기대 출력 예

```text
검색 호출 2곳 발견: shopbot/rag/tenant_retriever.py:search(필터 있음), …:ask_with_advisor(비교 경로, 검사한 값만 이어 붙임)
→ 진입점 TenantScopedRetriever.search 로 모음
tests/attack/test_tenant_isolation.py::test_shop_a_사용자는_shop_b_문서를_검색하지_못한다 PASSED
tests/attack/test_tenant_isolation.py::test_질문에_다른_테넌트_이름을_적어도_필터는_로그인_테넌트다 PASSED
tests/attack/test_tenant_isolation.py::test_shop_b_사용자도_shop_a_내부_문서를_못_본다 PASSED
```

실측: `samples/lab-app-py/_실측/3-5_pytest-before-tenant.txt`(수정 전 빨강), `3-7_pytest-tenant-after.txt`(수정 후 4 passed). Redis 질의 문자열(방법 B)은 `shopbot/rag/redis_store.py`의 `tenant_query`·`escape_tag`.

## 주의

- 생성된 코드에 `"tenantId == '" + 요청값 + "'"` 또는 `f"@tenantId:{{{req.tenant}}}"`처럼 **요청에서 온 값**이 들어가면 거절한다.
- "관리자는 모든 테넌트 검색" 같은 예외는 별도 함수·별도 권한 의존성으로 분리한다.
- 비교 경로 `/api/products/ask-advisor`는 HTTP 계약 시험이 고정한 이름이다(6장). 새 코드에 이 이름을 따라 쓰지 않는다.
