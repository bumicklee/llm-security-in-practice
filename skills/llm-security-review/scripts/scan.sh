#!/usr/bin/env bash
# 목적: FastAPI + LangChain 프로젝트를 grep으로 빠르게 훑어 출시 전 체크리스트(C01~C20)의 "단서"를 찾는다.
#       판정이 아니라 단서다. 최종 판정은 SKILL.md 절차대로 파일을 열어 사람이(또는 Claude가) 한다.
# 실행: bash scan.sh <프로젝트 폴더>      예) bash scan.sh samples/lab-app-py
# 출력: [OK] / [WARN] / [INFO] + 항목 ID + 근거(파일:줄). 마지막 줄에 개수 요약.
# 범위: 앱 코드(*.py, *.yaml, *.yml, *.toml, *.js, *.ts, *.tsx, *.html, *.jinja, *.j2)만 본다.
#       .venv·node_modules·tests·eval-kit·attack-kit·scripts·_golden·_실측·results 는 "앱 코드"에서 뺀다(테스트 근거는 C20에서 따로 센다).
#       주석·문서 문자열 속 단어도 걸릴 수 있다(단서이므로 그대로 둔다). 코드 줄만 보려는 검사는 nocomment로 거른다.
#       .env 파일은 열지 않는다(비밀). 트레이싱 변수는 설정 파일·compose·워크플로에서만 찾는다.
# macOS 기본 bash 3.2에서도 돈다. 네트워크를 쓰지 않는다. 파일을 고치지 않는다.
set -u
ROOT="${1:-.}"
if [ ! -d "$ROOT" ]; then echo "폴더 없음: $ROOT" >&2; exit 1; fi
ROOT="${ROOT%/}"

EXCL="--exclude-dir=.venv --exclude-dir=venv --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.git \
--exclude-dir=.pytest_cache --exclude-dir=tests --exclude-dir=test --exclude-dir=eval-kit --exclude-dir=attack-kit \
--exclude-dir=_실측 --exclude-dir=results --exclude-dir=.lab-run --exclude-dir=dist --exclude-dir=build \
--exclude-dir=scripts --exclude-dir=_golden"
INCL="--include=*.py --include=*.yaml --include=*.yml --include=*.toml --include=*.js --include=*.ts --include=*.tsx \
--include=*.html --include=*.jinja --include=*.j2"
# shellcheck disable=SC2086
G()  { grep -rEn $INCL $EXCL "$@" "$ROOT" 2>/dev/null; }          # 앱 코드
# shellcheck disable=SC2086
GP() { grep -rEn --include=*.py $EXCL "$@" "$ROOT" 2>/dev/null; } # 앱 Python만
first() { head -n "${1:-3}"; }
loc() { cut -d: -f1,2 | sed "s#^$ROOT/##" | tr '\n' ' '; }
nocomment() { grep -vE '^[^:]+:[0-9]+:[[:space:]]*(#|"""|\x27\x27\x27|//|\*)'; }   # 줄 머리가 주석·문서 문자열이면 뺀다
N_OK=0; N_WARN=0; N_INFO=0
say() {
  case "$1" in OK) N_OK=$((N_OK+1));; WARN) N_WARN=$((N_WARN+1));; INFO) N_INFO=$((N_INFO+1));; esac
  printf '[%s] %s %s\n' "$1" "$2" "$3"
}

# 0. 방어를 끄는 설정(수정 전 재현용 프로필인지 확인) — 맨 위에 모은다
off=$(G -i '^[[:space:]]*(secret_free_prompt|input_guard|output_schema|rag_guard|tenant_filter|rate_limit|token_budget|tool_authz|ssrf_guard|output_escape|pii_mask)[[:space:]]*:[[:space:]]*false' | first 12)
[ -n "$off" ] && say WARN C00 "방어 스위치 false(수정 전 재현용 프로필인지 확인): $(echo "$off" | loc)"

# C01 시스템 프롬프트 속 비밀 단서
sp=$(GP 'system_prompt[[:space:]]*=|SystemMessage\(|\("system",|SYSTEM_PROMPT' | first 5)
say INFO C01 "시스템 프롬프트 지정 위치: $(echo "$sp" | loc)"
sec=$(GP '(할인 코드|쿠폰 코드|비밀번호|내부 규칙|password[[:space:]]*[:=]|api[_-]?key[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{6,}|\bsk-[A-Za-z0-9])' | grep -viE 'FAKE|getenv|environ|os\.env|settings\.|# ' | first 5)
[ -n "$sec" ] && say WARN C01 "코드 속 비밀·내부 규칙 단서(프롬프트에 들어가는지 확인): $(echo "$sec" | loc)"

# C02 입력 검사: 에이전트 밖(의존성) 또는 before_agent
ig=$(GP 'def (guard_input|guard_[a-z_]+)\(|InputGuard|before_agent' | first 5)
if [ -n "$ig" ]; then say OK C02 "입력 검사 단서: $(echo "$ig" | loc)"; else say WARN C02 "입력 검사(의존성·before_agent) 단서 없음"; fi
bm=$(GP 'def before_model\(' | first 3)
[ -n "$bm" ] && say INFO C02 "before_model 구현(도구 루프마다 다시 돈다 — 입력 검사라면 위치 확인): $(echo "$bm" | loc)"
ml=$(GP 'max_length[[:space:]]*=[[:space:]]*[0-9]{1,4}[^0-9_]' | first 3)
[ -n "$ml" ] && say INFO C02 "짧은 Pydantic max_length(422가 먼저 나서 400 계약과 달라질 수 있음): $(echo "$ml" | loc)"
wl=$(GP -i 'blacklist|blocklist|forbidden_words|banned_words|BAD_WORDS' | first 3)
[ -n "$wl" ] && say INFO C02 "단어 목록식 방어 단서(한계 확인): $(echo "$wl" | loc)"

# C03 출력 스키마
os_=$(GP 'with_structured_output\(|ProviderStrategy\(|ToolStrategy\(|response_format[[:space:]]*=' | grep -v 'content_and_artifact' | nocomment | first 3)
if [ -n "$os_" ]; then say OK C03 "구조화 출력: $(echo "$os_" | loc)"; else say WARN C03 "구조화 출력(with_structured_output·response_format) 없음"; fi
rm_=$(GP 'response_model[[:space:]]*=' | first 3)
if [ -n "$rm_" ]; then say OK C03 "response_model: $(echo "$rm_" | loc)"; else say WARN C03 "엔드포인트 response_model 없음"; fi

# C04 나가는 답의 비밀·카나리 검사
lk=$(GP -i 'LeakDetector|canary|CANARY-' | first 3)
if [ -n "$lk" ]; then say OK C04 "출력 비밀·카나리 검사 단서: $(echo "$lk" | loc)"; else say WARN C04 "출력 비밀·카나리 검사 단서 없음"; fi

# C05·C06 RAG 수집 검사·문서 울타리·근거 ID
add=$(GP '\.add_documents\(|\.add_texts\(|from_documents\(|from_texts\(' | first 5)
[ -n "$add" ] && say INFO C05 "벡터 저장소에 넣는 곳(검사 단계 확인): $(echo "$add" | loc)"
scn=$(GP 'IngestionScanner|REVIEW_PENDING|\.scan\(' | first 3)
if [ -n "$add" ] && [ -z "$scn" ]; then say WARN C05 "넣기 전 검사 단서 없음"; elif [ -n "$scn" ]; then say OK C05 "수집 검사: $(echo "$scn" | loc)"; fi
fen=$(GP '<document|DocumentFencer|citedIds|cited_ids' | first 3)
if [ -n "$add" ] && [ -z "$fen" ]; then say WARN C06 "문서 울타리·근거 ID 단서 없음"; elif [ -n "$fen" ]; then say OK C06 "문서 울타리·근거 ID: $(echo "$fen" | loc)"; fi

# C07·C08 검색 필터와 진입점
ss=$(GP '\.similarity_search(_with_score)?\(|\.as_retriever\(' | cut -d: -f1 | sort -u)
n=$(echo "$ss" | grep -c . || true)
if [ "$n" -gt 1 ]; then say WARN C08 "검색 호출 파일 ${n}개(진입점 한 곳인지): $(echo "$ss" | sed "s#^$ROOT/##" | tr '\n' ' ')"
elif [ "$n" -eq 1 ]; then say OK C08 "검색 호출 한 곳: $(echo "$ss" | sed "s#^$ROOT/##")"; else say INFO C08 "similarity_search 없음(RAG 없음?)"; fi
if [ "$n" -ge 1 ]; then
  nf=""
  for hit in $(GP '\.similarity_search(_with_score)?\(' | nocomment | cut -d: -f1,2); do
    f="${hit%%:*}"; l="${hit##*:}"
    sed -n "${l},$((l+2))p" "$f" | grep -q 'filter' || nf="$nf ${f#$ROOT/}:$l"
  done
  [ -n "$nf" ] && say WARN C07 "filter 없이 검색하는 줄(테넌트 필터 확인):$nf"
fi
cat_f=$(GP "(tenant[A-Za-z_]*|filter)[^=]{0,40}(==|:)[^\n]{0,10}['\"][[:space:]]*\+|f['\"][^'\"]*(tenantId|tenant_id)[^'\"]*\{[a-z_.]*(req|request|body|payload|question|message)" | first 3)
[ -n "$cat_f" ] && say WARN C07 "필터 문자열 이어 붙이기·요청 값 사용 단서(값 검사 확인): $(echo "$cat_f" | loc)"
tf=$(GP 'tenant_filter|tenant_query|require_safe_tenant|metadata\.get\("tenantId"\)|metadata\["tenant' | first 3)
[ -n "$tf" ] && say OK C07 "테넌트 필터 단서: $(echo "$tf" | loc)"

# C09 로그인 필수
rt=$(GP '@(app|router)\.(post|get|put|delete|patch)\(' | cut -d: -f1 | sort -u)
for f in $rt; do
  if ! grep -qE 'Depends\(' "$f"; then say WARN C09 "라우트 파일에 Depends(로그인) 없음: ${f#$ROOT/}"; fi
done
au=$(GP 'HTTPBasic|OAuth2PasswordBearer|HTTPBearer|APIKeyHeader|def current_user' | first 2)
if [ -n "$au" ]; then say OK C09 "인증 의존성: $(echo "$au" | loc)"; else say WARN C09 "인증 의존성 단서 없음"; fi

# C10 레이트 리밋(키가 사용자 ID인지)
rl=$(GP -i 'rate_limit|RateLimit|slowapi|Limiter\(|limits\.strategies' | first 3)
if [ -n "$rl" ]; then say OK C10 "레이트 리밋 단서: $(echo "$rl" | loc)"; else say WARN C10 "레이트 리밋 단서 없음"; fi
ip=$(GP 'get_remote_address' | nocomment | first 3)
[ -n "$ip" ] && say WARN C10 "흔히 넘기는 get_remote_address는 IP 기준(key_func는 필수 인자, 사용자 ID로 바꿀지 확인): $(echo "$ip" | loc)"
ch_ip=$(GP 'request\.client\.host' | nocomment | first 3)
[ -n "$ch_ip" ] && say INFO C10 "클라이언트 IP를 쓰는 곳(레이트 리밋 키인지, 루프백 검사인지 확인): $(echo "$ch_ip" | loc)"

# C11 사용량 기록·토큰 한도
us=$(GP 'usage_metadata|token_usage|TokenBudget|wrap_model_call' | first 3)
if [ -n "$us" ]; then say OK C11 "사용량·토큰 한도 단서: $(echo "$us" | loc)"; else say WARN C11 "usage_metadata·토큰 한도 단서 없음(토큰을 재지 않음?)"; fi

# C12 대화 창·최대 출력·재시도·호출 상한
ra=$(G 'max_retries' | first 3)
if [ -n "$ra" ]; then say INFO C12 "재시도 설정: $(echo "$ra" | loc)"; else say WARN C12 "max_retries 설정 없음(openai SDK 기본 2 = 시도 3번, 앞단 재시도와 곱해짐)"; fi
mt=$(G 'max_tokens|max_completion_tokens' | first 2)
[ -z "$mt" ] && say WARN C12 "최대 출력 토큰 설정 없음"
tw=$(GP 'trim_messages|MessageWindow|last_n\(' | first 2)
[ -z "$tw" ] && say WARN C12 "대화 창(trim_messages 등) 단서 없음"
tl=$(GP 'ToolCallLimitMiddleware|ModelCallLimitMiddleware|recursion_limit' | first 3)
if [ -n "$tl" ]; then say OK C12 "도구·모델 호출 상한: $(echo "$tl" | loc)"; else say WARN C12 "도구·모델 호출 상한 단서 없음"; fi

# C13 캐시
ch=$(GP 'set_llm_cache|SemanticCache|RedisCache|InMemoryCache|lru_cache' | first 3)
[ -n "$ch" ] && say WARN C13 "캐시 사용(키에 사용자·테넌트가 들어가는지 확인): $(echo "$ch" | loc)"

# C14 비용 메트릭·경보
mx=$(GP 'prometheus_client|Counter\(|CostAlert|/metrics' | first 3)
if [ -n "$mx" ]; then say OK C14 "메트릭 단서: $(echo "$mx" | loc)"; else say WARN C14 "비용 메트릭·경보 단서 없음"; fi

# C15 도구 인자로 사용자 ID 받기 / ToolRuntime
tfiles=$(GP '^[[:space:]]*@tool\b|StructuredTool\.from_function|\(BaseTool\)' | cut -d: -f1 | sort -u)
for f in $tfiles; do
  bad=$(grep -nE 'def [a-z_]+\([^)]*\b(user_id|userId|owner_id|ownerId|tenant_id|tenantId|customer_id|customerId)\b' "$f" | first 2)
  [ -n "$bad" ] && say WARN C15 "도구 인자로 사용자·테넌트 ID(모델이 고른 값): ${f#$ROOT/}:$(echo "$bad" | cut -d: -f1 | tr '\n' ' ')"
done
rtm=$(GP 'ToolRuntime|InjectedToolArg|InjectedState|runtime\.context' | first 3)
if [ -n "$tfiles" ] && [ -z "$rtm" ]; then say WARN C15 "도구가 있는데 ToolRuntime·주입 인자 사용 없음"; elif [ -n "$rtm" ]; then say OK C15 "ToolRuntime·주입 인자: $(echo "$rtm" | loc)"; fi

# C16 승인·허용 목록
ap=$(GP -i 'approval|approve|HumanInTheLoopMiddleware|interrupt\(' | cut -d: -f1 | sort -u | first 3)
if [ -n "$tfiles" ] && [ -z "$ap" ]; then say WARN C16 "승인 단서 없음 — 변경·금전 도구가 있는지 확인"; elif [ -n "$ap" ]; then say OK C16 "승인 단서: $(echo "$ap" | sed "s#^$ROOT/##" | tr '\n' ' ')"; fi
al=$(GP -i 'ToolAllowlist|tool_allowlist|verify_tool_allowlist|allowed_tools' | first 3)
if [ -n "$tfiles" ] && [ -z "$al" ]; then say WARN C16 "도구 허용 목록 단서 없음"; elif [ -n "$al" ]; then say OK C16 "도구 허용 목록: $(echo "$al" | loc)"; fi

# C17 도구 안 HTTP 호출·리다이렉트·MCP
for f in $tfiles; do
  if grep -qE 'httpx2?\.|requests\.(get|post)|urllib\.request|aiohttp' "$f" && ! grep -qiE 'Guard|allowlist|allowed_hosts|허용' "$f"; then
    say WARN C17 "도구에서 HTTP 호출(SSRF 검사 확인): ${f#$ROOT/}"
  fi
done
fr=$(GP 'follow_redirects[[:space:]]*=[[:space:]]*True' | first 3)
[ -n "$fr" ] && say WARN C17 "리다이렉트 자동 따라가기(follow_redirects=True): $(echo "$fr" | loc)"
sg=$(GP 'UrlFetchGuard|getaddrinfo|is_private|is_public' | first 3)
[ -n "$sg" ] && say OK C17 "SSRF 검사 단서: $(echo "$sg" | loc)"
mc=$(GP 'from mcp |import mcp|langchain_mcp_adapters|MultiServerMCPClient' | first 3)
if [ -n "$mc" ]; then
  mg=$(GP -i 'McpToolGate|mcp_allowed_tools' | first 2)
  if [ -n "$mg" ]; then say OK C17 "MCP 도구 게이트: $(echo "$mg" | loc)"; else say WARN C17 "MCP 사용 — 받은 도구 허용 목록 게이트 단서 없음: $(echo "$mc" | loc)"; fi
fi

# C18 HTML로 그리기
ih=$(G 'innerHTML|dangerouslySetInnerHTML|v-html|\|[[:space:]]*safe\b|Markup\(' | first 3)
[ -n "$ih" ] && say WARN C18 "HTML로 그리는 곳(모델 출력인지, 이스케이프 스위치가 있는지 확인): $(echo "$ih" | loc)"
es=$(G 'textContent|html\.escape|HtmlOutputEscaper' | first 2)
[ -n "$es" ] && say OK C18 "이스케이프 단서: $(echo "$es" | loc)"

# C19 마스킹·원문 로그·트레이싱
pm=$(GP 'PiiMasker|PIIMiddleware|def mask\(' | first 3)
if [ -n "$pm" ]; then say OK C19 "마스킹 단서: $(echo "$pm" | loc)"; else say WARN C19 "개인정보 마스킹 단서 없음"; fi
dbg=$(GP 'set_debug\(True\)|set_verbose\(True\)' | grep -E '^[^:]+:[0-9]+:[[:space:]]*([A-Za-z_][A-Za-z0-9_.]*\.)?set_(debug|verbose)\(True\)' | first 3)   # 문장으로 부른 줄만
[ -n "$dbg" ] && say WARN C19 "LangChain 디버그 출력 켬(프롬프트 원문이 로그로): $(echo "$dbg" | loc)"
tr_on=$(grep -rEn --include=*.yaml --include=*.yml --include=*.toml --include=*.sh --include=Dockerfile --include=*.json \
        --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git \
        '(LANGSMITH_TRACING(_V2)?|LANGCHAIN_TRACING(_V2)?)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?(true|True|1)' "$ROOT" 2>/dev/null | first 3)
[ -n "$tr_on" ] && say WARN C19 "트레이싱 환경 변수를 켜는 설정(원문이 밖으로): $(echo "$tr_on" | loc)"
tg=$(GP 'LANGSMITH_TRACING|LANGCHAIN_TRACING' | first 2)
if [ -n "$tg" ]; then say OK C19 "시작할 때 트레이싱 변수 검사 단서(fail closed인지 확인): $(echo "$tg" | loc)"; else say WARN C19 "트레이싱 변수 시작 검사 없음(켜져 있으면 시작 거부 권장)"; fi
lp=$(GP 'log(ger)?\.(info|debug|warning)\([^)]*(prompt|messages|content)' | first 3)
[ -n "$lp" ] && say INFO C19 "프롬프트·메시지를 찍을 수 있는 로그 줄(원문인지 확인): $(echo "$lp" | loc)"

# C20 요청 ID·CI·테스트
rid=$(GP -i 'X-Request-Id|contextvars|request_id' | first 2)
if [ -n "$rid" ]; then say OK C20 "요청 ID 단서: $(echo "$rid" | loc)"; else say WARN C20 "요청 ID(감사 로그 묶기) 단서 없음"; fi
if ls "$ROOT"/.github/workflows/*.y*ml >/dev/null 2>&1; then
  wf=$(grep -lE 'pytest' "$ROOT"/.github/workflows/*.y*ml 2>/dev/null | sed "s#^$ROOT/##" | tr '\n' ' ')
  if [ -n "$wf" ]; then say OK C20 "pytest를 도는 워크플로: $wf"; else say WARN C20 "워크플로에 pytest 잡 없음"; fi
else say WARN C20 ".github/workflows 없음(PR마다 공격 테스트?)"; fi
nt=$(find "$ROOT" -type f -name 'test_*.py' ! -path '*/.venv/*' ! -path '*/node_modules/*' 2>/dev/null | grep -c . || true)
say INFO C20 "test_*.py 파일 ${nt}개"

# 부가(체크리스트 밖): Claude Code 훅이 fail closed인지
CS="$ROOT/.claude/settings.json"
if [ -f "$CS" ]; then
  if grep -q '"hooks"' "$CS"; then
    grep -q '"onFailure"[[:space:]]*:[[:space:]]*"block"' "$CS" && say OK H01 "훅 onFailure: block(Claude Code v2.1.295+)" || say WARN H01 "훅에 \"onFailure\": \"block\" 없음(훅이 실패하면 동작이 그대로 진행)"
    grep -q '"args"' "$CS" && say OK H02 "훅 exec 형식(args)" || say INFO H02 "훅이 셸 형식(경로 자리표시는 exec 형식 args 권장)"
  else say INFO H01 ".claude/settings.json에 hooks 없음"; fi
  for h in "$ROOT"/.claude/hooks/*.sh; do
    [ -f "$h" ] || continue
    grep -q 'exit 2' "$h" || say WARN H03 "훅 스크립트에 exit 2(차단) 없음: ${h#$ROOT/}"
  done
else
  say INFO H01 ".claude/settings.json 없음(Claude Code 훅 점검 생략)"
fi

echo "요약: OK ${N_OK} · WARN ${N_WARN} · INFO ${N_INFO}. 단서일 뿐이다. checklist.md의 판정 규칙으로 파일을 열어 확인한다."
