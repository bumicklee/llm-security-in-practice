"""가짜 요금 대시보드(7장·8장). 가짜 LLM의 /usage를 읽어 "가짜 단가 × 토큰"으로 예상 청구액을 보여 준다.

최근 120초 토큰 그래프와 하루 예산선(가짜 10,000원)을 그린다. 단가·예산은 모두 가짜 값. 표준 라이브러리만.
실행: python -I tools/bill_board.py   → http://127.0.0.1:8090
      FAKE_LLM_URL=http://fake-llm:8070 BIND=0.0.0.0 (컨테이너 안에서만)
"""
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAKE_INPUT_KRW_PER_1K = 10.0   # 가짜 단가
FAKE_OUTPUT_KRW_PER_1K = 30.0  # 가짜 단가
FAKE_DAILY_BUDGET_KRW = 10_000  # 가짜 예산
LLM = os.environ.get("FAKE_LLM_URL", "http://127.0.0.1:8070")
EMPTY = '{"requests":0,"promptTokens":0,"completionTokens":0,"perSecond":[]}'

PAGE = """
<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>가짜 요금 대시보드</title>
<style>body{font-family:sans-serif;margin:24px} .big{font-size:40px;font-weight:bold} .warn{color:#c00}</style></head>
<body><h1>가짜 요금 대시보드 <small>(가짜 단가: 입력 $IN원/1K, 출력 $OUT원/1K)</small></h1>
<p>요청 수 <b id="req">0</b> · 입력 토큰 <b id="pt">0</b> · 출력 토큰 <b id="ct">0</b></p>
<p>예상 청구액 <span class="big" id="krw">0원</span> / 하루 예산 $BUDGET원 <span id="alert"></span></p>
<svg id="g" width="720" height="200" style="border:1px solid #ccc"></svg>
<p>최근 120초, 초당 토큰. 빨간 선 = 초당 한도 예시(500토큰).</p>
<script>
async function tick(){
  const d = await (await fetch('/data')).json();
  const krw = d.promptTokens/1000*$IN + d.completionTokens/1000*$OUT;
  document.getElementById('req').textContent = d.requests;
  document.getElementById('pt').textContent = d.promptTokens;
  document.getElementById('ct').textContent = d.completionTokens;
  document.getElementById('krw').textContent = Math.round(krw).toLocaleString() + '원';
  const a = document.getElementById('alert');
  a.textContent = krw >= $BUDGET ? ' 예산 초과' : (krw >= $BUDGET*0.8 ? ' 80% 경보' : (krw >= $BUDGET*0.5 ? ' 50% 경보' : ''));
  a.className = krw >= $BUDGET*0.5 ? 'warn' : '';
  const now = Math.floor(Date.now()/1000), map = new Map(d.perSecond.map(p => [p[0], p[1]]));
  const g = document.getElementById('g'); g.replaceChildren();
  const ns = 'http://www.w3.org/2000/svg';
  for (let i = 0; i < 120; i++) {
    const v = map.get(now - 119 + i) || 0, h = Math.min(190, v / 10);
    const r = document.createElementNS(ns, 'rect');
    r.setAttribute('x', i*6); r.setAttribute('y', 200-h); r.setAttribute('width', 5); r.setAttribute('height', h);
    r.setAttribute('fill', '#36c'); g.appendChild(r);
  }
  const l = document.createElementNS(ns, 'line');
  l.setAttribute('x1', 0); l.setAttribute('x2', 720); l.setAttribute('y1', 150); l.setAttribute('y2', 150);
  l.setAttribute('stroke', '#c00'); g.appendChild(l);
}
setInterval(tick, 1000); tick();
</script></body></html>
""".lstrip("\n")


def page() -> str:
    return (PAGE.replace("$IN", f"{FAKE_INPUT_KRW_PER_1K:.0f}").replace("$OUT", f"{FAKE_OUTPUT_KRW_PER_1K:.0f}")
            .replace("$BUDGET", f"{FAKE_DAILY_BUDGET_KRW:.0f}"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/data"):
            try:
                with urllib.request.urlopen(LLM + "/usage", timeout=2) as r:
                    body, ctype = r.read().decode("utf-8"), "application/json"
            except OSError:
                body, ctype = EMPTY, "application/json"
        else:
            body, ctype = page(), "text/html"
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *args):
        pass


def main():
    bind = os.environ.get("BIND", "127.0.0.1")
    port = int(os.environ.get("BILL_PORT", "8090"))
    srv = ThreadingHTTPServer((bind, port), Handler)
    srv.daemon_threads = True
    print(f"[bill-board] http://{bind}:{port} (가짜 단가·가짜 예산)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
