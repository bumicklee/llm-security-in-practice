# 프롬프트: RAG 문서 수집 경로 점검

- **쓰는 곳:** 5장 5.2~5.3, 수업 3-2·3-3
- **도구:** Claude Code
- **목적:** "누가 쓴 글이 벡터 저장소에 들어가는가"를 끝까지 따라가 출처·신뢰 등급·검사 단계가 있는지 표로 만든다.

## 프롬프트 본문

```text
이 프로젝트에서 벡터 저장소에 문서를 넣는 모든 호출(add_documents, add_texts, from_documents, from_texts, 직접 만든 저장 함수)을 찾아라. 코드는 고치지 마라.

각 호출마다:
| 호출 위치(파일:함수) | 문서 출처(누가 쓴 글?) | 메타데이터에 남기는 키 | 넣기 전 검사 | 검토 대기열 | 비고 |

그다음:
1) 고객이 쓴 글(리뷰·게시글·업로드)이 검사 없이 들어가는 경로를 모두 나열
2) 메타데이터에 {필수_키} 가 빠진 곳
3) 검색해서 프롬프트에 넣는 코드에서 문서를 데이터 블록으로 감싸는지, 문서 ID를 남기는지, 답에 근거 ID(citedIds)를 받는지
4) 시험용·관리용 엔드포인트가 정상 수집 함수를 건너뛰고 저장소에 바로 넣는지
5) 고칠 순서 3개
공격 예문은 쓰지 마라. 필요하면 [ATTACK-RAG-01: 리뷰 속 숨은 지시 유형] 처럼 자리 표시만.
```

## 입력 예

| 변수 | 값 |
| --- | --- |
| `{필수_키}` | `tenantId, visibility, source, trust` |
| 범위 | `samples/lab-app-py/shopbot`, `samples/lab-app-py/labcore` |

## 기대 출력 예

```text
| shopbot/rag/ingestion.py:ingest_review | 고객(로그인 사용자) | tenantId, visibility, source(review:<id>), trust(CUSTOMER) | IngestionScanner.scan | 202 REVIEW_PENDING(lab.pending_reviews) | rag_guard=false면 검사 생략 |
| shopbot/rag/store.py:build_memory_store | 직원·공식(시드) | tenantId, visibility, source, trust | 없음 | 없음 | KnowledgeStore.seed_docs(신뢰) |
| shopbot/eval/router.py:fixtures | 시험용 리뷰(eval 프로필) | ingest_review와 같음 | ingest_review를 지남 | 같음 | 정상 수집 경로를 쓴다(좋음) |
1) 검사 없이 들어가는 고객 글 경로: 없음(rag_guard=true 기준)
```

수정 후 실제 동작은 `samples/lab-app-py/_실측/3-3_review-scan-after.txt`(리뷰 3개 중 1개만 `REVIEW_PENDING` 202)에 있다.

## 주의

- 검사기는 "막기"보다 "표시하고 사람에게 보내기"가 기본이다. 무조건 차단하는 코드를 만들게 하지 않는다.
- 랩 전용 표지(`[ATTACK-RAG-`) 탐지는 실서비스에서는 분류기·사람 검토로 바뀐다.
- 외부 벡터 저장소(Redis 등)를 쓰면 저장소에 직접 넣는 배치 스크립트도 찾게 한다. 앱 밖 경로가 가장 자주 빠진다.
