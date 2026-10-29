// 목적: 채팅 화면 동작. 가짜 비밀번호 FAKE-pass-0000(랩 전용).
let escapeOutput = true;
const auth = () => 'Basic ' + btoa(document.getElementById('user').value + ':FAKE-pass-0000');

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { 'Authorization': auth(), 'Content-Type': 'application/json' } });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body, requestId: res.headers.get('X-Request-Id') };
}

function show(cls, text) {
  const d = document.createElement('div');
  d.className = cls;
  if (escapeOutput) d.textContent = text;   // [수정 후] 글자로만
  else d.innerHTML = text;                  // [수정 전] 모델 글을 HTML로 해석 → 11장 재현
  document.getElementById('log').appendChild(d);
}

async function refresh() {
  const flags = await api('/api/lab/flags');
  escapeOutput = flags.body.outputEscape !== false;
  document.getElementById('mode').textContent = escapeOutput ? '(수정 후)' : '(수정 전: before 프로필)';
  const u = await api('/api/lab/usage');
  document.getElementById('tokens').textContent = u.body.tokensToday ?? 0;
  const a = await api('/api/approvals');
  const ul = document.getElementById('approvals');
  ul.replaceChildren();
  (a.body || []).forEach(p => {
    const li = document.createElement('li');
    if (p.toolName === 'issueCoupon') {   // 22장: 쿠폰은 같은 매장 직원이 승인한다. 고객 화면에는 버튼이 없다
      li.textContent = `주문 ${p.orderId} 쿠폰 ${p.amountKrw}원 요청 · 직원 확인 중`;
      ul.appendChild(li);
      return;
    }
    li.textContent = `주문 ${p.orderId} 취소 요청 `;
    for (const [label, act] of [['승인', 'approve'], ['거절', 'reject']]) {
      const b = document.createElement('button');
      b.textContent = label;
      b.onclick = async () => { const r = await api(`/api/approvals/${p.id}/${act}`, { method: 'POST' }); show('bot', r.body.message); refresh(); };
      li.appendChild(b);
    }
    ul.appendChild(li);
  });
}

document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const m = document.getElementById('msg').value;
  const me = document.createElement('div'); me.className = 'me'; me.textContent = m;
  document.getElementById('log').appendChild(me);
  const r = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: m }) });
  if (r.status === 200) show('bot', r.body.answer);
  else { const d = document.createElement('div'); d.className = 'err'; d.textContent = `${r.status} ${r.body.answer || r.body.error || ''} (요청 ID ${r.requestId})`; document.getElementById('log').appendChild(d); }
  refresh();
};
// 상품 질문: 답 + "근거: 문서 ID" (5장 5.5). 근거가 없으면 서버가 "확인할 수 없습니다"로 바꾼다.
document.getElementById('qa').onsubmit = async (e) => {
  e.preventDefault();
  const r = await api('/api/products/ask', { method: 'POST', body: JSON.stringify({ question: document.getElementById('q').value }) });
  const out = document.getElementById('qaOut');
  out.replaceChildren();
  const a = document.createElement('div'); a.className = 'bot'; a.textContent = r.body.answer || `${r.status}`;
  const c = document.createElement('div'); c.className = 'cite'; c.textContent = '근거: ' + ((r.body.citedIds || []).join(', ') || '없음');
  out.append(a, c);
};

// 리뷰 등록: 검사기에 걸리면 202 + 노란 경고 배지(5장 5.3)
document.getElementById('rv').onsubmit = async (e) => {
  e.preventDefault();
  const r = await api('/api/reviews', { method: 'POST', body: JSON.stringify({ text: document.getElementById('rt').value }) });
  const out = document.getElementById('rvOut');
  out.replaceChildren();
  const d = document.createElement('div');
  if (r.status === 202) {
    const b = document.createElement('span'); b.className = 'badge'; b.textContent = '검토 대기';
    d.append(b, document.createTextNode(' ' + (r.body.findings || []).map(f => f.kind).join(', ')));
  } else {
    d.textContent = `${r.status} ${r.body.status || ''} ${r.body.id || ''}`;
  }
  out.appendChild(d);
};

document.getElementById('user').onchange = refresh;
refresh();
