/* 루트 최저가 주유소 — 프런트엔드 */

const $ = (id) => document.getElementById(id);
const won = (n) => (n == null ? '—' : n.toLocaleString('ko-KR'));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const KIND = { road: '일반도로', expy: '고속도로' };
const FUEL_NAME = { gasoline: '휘발유', diesel: '경유', premium: '고급휘발유' };
const ALT = { 농협알뜰: 1, 자영알뜰: 1, 고속도로휴게소: 1 };
const COORD = /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/;

const ICON_MAP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11Z"/><circle cx="12" cy="10" r="2.6"/></svg>';
const ICON_TEL = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5Z"/></svg>';

/* ---------------- 상태 ---------------- */
const S = {
  fuel: 'gasoline', off: 5, self: false, h24: false, alt: false,
  brand: '', reg: '', vol: 40, q: '', open: {}, focus: null,
};
let PLAN = null;
let hasTmapKey = false;

try {
  const saved = JSON.parse(localStorage.getItem('route-fuel-v1') || 'null');
  if (saved) for (const k of ['fuel', 'off', 'self', 'h24', 'alt', 'vol']) if (k in saved) S[k] = saved[k];
} catch { /* 저장값이 없거나 못 읽으면 기본값으로 */ }
function save() {
  try {
    localStorage.setItem('route-fuel-v1', JSON.stringify(
      { fuel: S.fuel, off: S.off, self: S.self, h24: S.h24, alt: S.alt, vol: S.vol }));
  } catch { /* 저장 실패는 무시 — 조회에는 영향 없다 */ }
}

/* ---------------- 경로 입력 ---------------- */
let stops = [
  { role: 'start', label: '출발지', text: '', picked: null },
  { role: 'goal', label: '도착지', text: '', picked: null },
];
let maxWaypoints = 5;

function renderStops() {
  const box = $('stops');
  box.innerHTML = '';
  stops.forEach((stop, i) => {
    const row = document.createElement('div');
    row.className = `stop ${stop.role}`;
    const badge = stop.role === 'start' ? '출발' : stop.role === 'goal' ? '도착' : String(i);
    row.innerHTML = `
      <span class="badge">${badge}</span>
      <div class="combo">
        <input type="text" autocomplete="off" spellcheck="false"
               placeholder="${esc(stop.label)} — 장소명 또는 위도,경도"
               aria-label="${esc(stop.label)}" value="${esc(stop.text)}">
        <span class="picked"></span>
        <ul class="sugg" hidden></ul>
      </div>
      ${stop.role === 'via' ? '<button class="kill" type="button" aria-label="경유지 삭제">×</button>' : '<span></span>'}`;
    box.appendChild(row);

    const input = row.querySelector('input');
    const list = row.querySelector('.sugg');
    stop.el = { input, picked: row.querySelector('.picked') };
    paintPicked(stop);
    input.addEventListener('input', () => onType(stop, input, list));
    input.addEventListener('focus', () => { if (list.children.length) list.hidden = false; });
    input.addEventListener('blur', () => setTimeout(() => { list.hidden = true; }, 150));
    row.querySelector('.kill')?.addEventListener('click', () => {
      stops = stops.filter((s) => s !== stop);
      renderStops();
    });
  });
  $('addStop').disabled = stops.filter((s) => s.role === 'via').length >= maxWaypoints;
}

let typeTimer;
function onType(stop, input, list) {
  stop.text = input.value;
  const coord = stop.text.match(COORD);
  if (coord) {
    setPicked(stop, { name: stop.text.trim(), lat: Number(coord[1]), lon: Number(coord[2]) });
    list.hidden = true;
    return;
  }
  stop.picked = null;
  paintPicked(stop);
  clearTimeout(typeTimer);
  if (stop.text.trim().length < 2) { list.hidden = true; return; }
  typeTimer = setTimeout(async () => {
    if (!hasTmapKey) {
      list.innerHTML = '<li class="s-empty">TMAP 키가 없어 장소 검색을 쓸 수 없습니다. 위도,경도를 직접 입력하세요.</li>';
      list.hidden = false;
      return;
    }
    try {
      const res = await fetch(`/api/poi?q=${encodeURIComponent(stop.text.trim())}`);
      const data = await res.json();
      const items = data.results || [];
      list.innerHTML = items.length
        ? items.map((p, i) => `<li><button type="button" data-i="${i}">
             <span class="s-nm">${esc(p.name)}</span>
             <span class="s-ad">${esc(p.roadAddress || p.address)}</span></button></li>`).join('')
        : '<li class="s-empty">검색 결과가 없습니다.</li>';
      list.hidden = false;
      list.querySelectorAll('button').forEach((b) => b.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const p = items[Number(b.dataset.i)];
        setPicked(stop, { name: p.name, lat: p.lat, lon: p.lon }, { syncInput: true });
        list.hidden = true;
      }));
    } catch {
      list.innerHTML = '<li class="s-empty">검색에 실패했습니다.</li>';
      list.hidden = false;
    }
  }, 250);
}

/** 좌표를 입력하는 도중에도 포커스가 튀지 않도록, 확정 표시만 제자리에서 갱신한다. */
function paintPicked(stop) {
  const el = stop.el?.picked;
  if (!el) return;
  el.className = `picked ${stop.picked ? '' : 'none'}`;
  el.textContent = stop.picked
    ? `📍 ${stop.picked.name} · ${stop.picked.lat.toFixed(5)}, ${stop.picked.lon.toFixed(5)}`
    : '아직 지정되지 않음';
}

function setPicked(stop, picked, { syncInput = false } = {}) {
  stop.picked = picked;
  if (syncInput) {
    stop.text = picked.name;
    if (stop.el?.input) stop.el.input.value = picked.name;
  }
  paintPicked(stop);
}

$('addStop').addEventListener('click', () => {
  const goalAt = stops.findIndex((s) => s.role === 'goal');
  stops.splice(goalAt, 0, { role: 'via', label: '경유지', text: '', picked: null });
  renderStops();
});

/* ---------------- 조회 ---------------- */
function banner(el, html) {
  const node = $(el);
  node.innerHTML = html;
  node.hidden = !html;
}

$('search').addEventListener('click', async () => {
  const missing = stops.filter((s) => !s.picked);
  if (missing.length) {
    banner('errorBanner', `<b>${esc(missing.map((m) => m.label).join(', '))}</b>를 지정해 주세요.`);
    return;
  }
  banner('errorBanner', '');
  $('search').disabled = true;
  $('progress').innerHTML = '<span class="spinner"></span> 경로와 유가를 모으는 중…';
  try {
    const body = {
      start: stops[0].picked,
      goal: stops[stops.length - 1].picked,
      waypoints: stops.filter((s) => s.role === 'via').map((s) => s.picked),
    };
    const res = await fetch('/api/plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `서버 오류 ${res.status}`);
    PLAN = data;
    $('results').hidden = false;
    buildFilters();
    renderStamp();
    render();
    if (data.warnings?.length) banner('errorBanner', data.warnings.map(esc).join('<br>'));
    $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    banner('errorBanner', `<b>조회 실패</b> ${esc(err.message)}`);
  } finally {
    $('search').disabled = false;
    $('progress').textContent = '';
  }
});

/* ---------------- 결과 ---------------- */
function renderStamp() {
  const el = $('stamp');
  const r = PLAN.route;
  const bits = [`총 <b class="num">${r.totalKm}</b> km`];
  if (r.totalMin) bits.push(`약 ${Math.floor(r.totalMin / 60)}시간 ${r.totalMin % 60}분`);
  if (r.tollFare) bits.push(`통행료 ${won(r.tollFare)}원`);
  bits.push(`${PLAN.regions.length}개 시·군 · 주유소 ${PLAN.counts.collected}곳 수집`);
  if (PLAN.asOf) bits.push(`기준 <b class="num">${esc(PLAN.asOf)}</b>`);
  el.innerHTML = bits.join(' · ');
  $('railTitle').textContent = `구간별 최저가 · ${r.totalKm}km`;
}

function buildFilters() {
  for (const [id, key] of [['brand', 'brand'], ['reg', 'region']]) {
    const sel = $(id);
    const seen = new Map();
    for (const s of PLAN.stations) {
      if (s.blocked) continue;
      seen.set(s[key], (seen.get(s[key]) || 0) + 1);
    }
    let order = [...seen.keys()];
    if (id === 'brand') order.sort((a, b) => seen.get(b) - seen.get(a));
    sel.innerHTML = '<option value="">전체</option>'
      + order.map((v) => `<option value="${esc(v)}">${esc(v)} (${seen.get(v)})</option>`).join('');
    sel.value = '';
  }
  S.brand = ''; S.reg = ''; S.open = {}; S.focus = null;
}

function pass(s) {
  const p = s.prices[S.fuel];
  if (p == null || s.blocked) return false;
  if (S.reg && s.region !== S.reg) return false;
  if (!s.serviceArea && s.offRouteKm > S.off && S.off < 21) return false;
  if (S.self && !s.self) return false;
  if (S.h24 && !s.open24h) return false;
  if (S.alt && !ALT[s.brand]) return false;
  if (S.brand && s.brand !== S.brand) return false;
  if (S.q && !`${s.name} ${s.address} ${s.brand}`.toLowerCase().includes(S.q.toLowerCase())) return false;
  return true;
}

function row(s, rank, lo, hi) {
  const p = s.prices[S.fuel];
  const dlt = p - lo;
  const w = hi > lo ? Math.max(dlt ? 3 : 0, Math.round((100 * dlt) / (hi - lo))) : 0;
  const other = S.fuel === 'gasoline'
    ? (s.prices.diesel != null ? `경유 ${won(s.prices.diesel)}` : '')
    : (s.prices.gasoline != null ? `휘발유 ${won(s.prices.gasoline)}` : '');
  const q = encodeURIComponent(`${s.name} ${s.address.split(' ').slice(0, 3).join(' ')}`);
  return `<li class="st${rank === 1 ? ' top' : ''}">
    <span class="rk">${rank}</span>
    <div class="info"><div class="nm">${esc(s.name)}
      ${rank === 1 ? `<span class="chip cheap">${dlt === 0 ? '루트 최저' : '구간 최저'}</span>` : ''}
      <span class="chip">${esc(s.brand)}</span>
      ${s.serviceArea ? '<span class="chip sa">휴게소</span>' : ''}
      ${s.needsExit ? '<span class="chip ex">IC 밖</span>' : ''}
      ${s.self ? '<span class="chip self">셀프</span>' : ''}
      ${s.open24h ? '<span class="chip h24">24H</span>' : ''}
    </div><div class="sub">
      <span class="off">${s.serviceArea ? '루트 위 휴게소' : `루트 +${s.offRouteKm.toFixed(1)}km`}</span>
      <span>${esc(s.address)}</span></div></div>
    <div class="meter" title="${S.vol}L 주유 시 루트 최저가보다 ${won(dlt * S.vol)}원 더 냄">
      <span class="mlab${dlt ? '' : ' zero'}">${dlt === 0 ? '루트 최저' : `+${won(dlt * S.vol)}원`}</span>
      <span class="bar"><i style="width:${w}%"></i></span></div>
    <div class="pr"><b>${won(p)}</b><u>원</u><em>${esc(other)}</em></div>
    <div class="acts">
      <a href="https://map.kakao.com/link/search/${q}" target="_blank" rel="noopener"
         title="지도에서 보기" aria-label="${esc(s.name)} 지도에서 보기">${ICON_MAP}</a>
      ${s.phone ? `<a href="tel:${esc(s.phone.replace(/[^0-9]/g, ''))}" title="${esc(s.phone)}"
         aria-label="${esc(s.name)} 전화">${ICON_TEL}</a>` : ''}
    </div></li>`;
}

function board(title, hint, list, lo, hi, key, limit) {
  const id = key ? `leg-${key}` : 'top';
  if (!list.length) {
    return `<section class="board" id="${id}"><header><h2>${title}</h2><span class="hint">${hint}</span></header>
      <p class="empty-msg">이탈 거리를 넓히거나 필터를 풀어보세요.</p></section>`;
  }
  const open = key && S.open[key];
  const shown = open ? list : list.slice(0, limit);
  let html = `<section class="board" id="${id}"><header><h2>${title}</h2><span class="hint">${hint}</span></header>
    <ul class="stations">${shown.map((s, i) => row(s, i + 1, lo, hi)).join('')}</ul>`;
  if (key && list.length > limit) {
    html += `<button class="more" data-leg="${key}">${open ? '접기 ▴' : `이 구간 ${list.length}곳 모두 보기 ▾`}</button>`;
  }
  return `${html}</section>`;
}

function tile(cls, lbl, big, unit, sub) {
  return `<div class="tile ${cls}"><span class="lbl">${lbl}</span>
    <span class="big">${big}${unit ? `<u>${unit}</u>` : ''}</span>
    <span class="sub" title="${esc(sub)}">${esc(sub)}</span></div>`;
}

function render() {
  if (!PLAN) return;
  const segs = PLAN.route.segments;
  const fuelName = FUEL_NAME[S.fuel];
  const all = PLAN.stations.filter(pass)
    .sort((a, b) => a.prices[S.fuel] - b.prices[S.fuel] || a.offRouteKm - b.offRouteKm);
  const lo = all.length ? all[0].prices[S.fuel] : 0;
  const hi = all.length ? all[all.length - 1].prices[S.fuel] : 0;
  const avg = all.length ? all.reduce((a, s) => a + s.prices[S.fuel], 0) / all.length : 0;

  $('count').innerHTML = `조건 충족 <b>${all.length}</b> / 이용 가능 ${PLAN.counts.usable}곳`;

  const bySeg = segs.map(() => []);
  for (const s of all) bySeg[s.segment]?.push(s);

  const best = all[0];
  $('tiles').innerHTML = all.length
    ? tile('hero', `루트 최저가 · ${fuelName}`, won(lo), '원', `${best.name} · ${best.region}`)
      + tile('', '루트 평균가', won(Math.round(avg)), '원', `최저가보다 ${won(Math.round(avg - lo))}원 비쌈`)
      + tile('save', `${S.vol}L 기준 최대 절약`, won(Math.round((hi - lo) * S.vol)), '원',
        `최고 ${won(hi)}원 → 최저 ${won(lo)}원`)
      + tile('text', '최저가 구간', `${segs[best.segment].id}. ${segs[best.segment].name}`, '',
        best.serviceArea ? '고속도로 휴게소 · 루트 위' : `루트 이탈 ${best.offRouteKm.toFixed(1)}km`)
    : '<div class="tile"><span class="lbl">결과 없음</span><span class="big">0</span><span class="sub">필터를 풀어보세요</span></div>';

  const mins = bySeg.map((l) => (l.length ? l[0].prices[S.fuel] : null));
  const valid = mins.filter((v) => v != null);
  const mn = Math.min(...valid), mx = Math.max(...valid);
  $('rail').innerHTML = segs.map((g, i) => {
    const v = mins[i], n = bySeg[i].length;
    const t = v == null || mx === mn ? 0 : (mx - v) / (mx - mn);
    const w = v == null ? 0 : Math.round(10 + 90 * t);
    return `<li><button class="leg-btn${v != null && v === mn ? ' best' : ''}${n ? '' : ' empty'}"
        data-goto="${g.id}"${S.focus === g.id ? ' aria-current="true"' : ''}>
      <span class="mk">${g.id}</span>
      <span class="leg-body"><span class="leg-nm">${esc(g.name)}<span>${n}곳</span></span>
      <span class="leg-price"><b>${v == null ? '—' : won(v)}</b>${v == null ? '' : '원'}
        <span class="kind ${g.kind}">${KIND[g.kind]} ${g.lengthKm}km</span></span>
      <span class="trk"><i style="width:${w}%"></i></span></span></button></li>`;
  }).join('');

  let html = board('루트 전체 최저가 TOP 12',
    `${fuelName} · 루트 이탈 ${S.off >= 21 ? '제한 없음' : `${S.off}km 이내`} · 막대는 ${S.vol}L 주유 시 <b>루트 최저가 대비 추가 비용</b>`,
    all.slice(0, 12), lo, hi, null, 12);

  segs.forEach((g, i) => {
    const list = bySeg[i];
    const title = `<span class="legmark">${g.id}</span> ${esc(g.name)}<span class="kind ${g.kind}">${KIND[g.kind]} ${g.lengthKm}km</span>`;
    let hint;
    if (!list.length) {
      hint = g.kind === 'expy'
        ? '고속도로 주행 구간입니다. 진행 방향 휴게소 주유소만 이용할 수 있는데, 지금 조건에 맞는 곳이 없습니다.'
        : '조건에 맞는 주유소가 없습니다.';
    } else {
      hint = `${esc(g.roadLabel)} · ${list.length}곳 중 최저 ${won(list[0].prices[S.fuel])}원 · ${S.vol}L 기준 <b>${won(Math.round((list[0].prices[S.fuel] - lo) * S.vol))}원</b> 더 냄 (루트 최저가 대비)`;
      if (g.kind === 'expy') hint = `<b>고속도로 주행 구간</b> — 진행 방향 휴게소만 이용 가능 · ${hint}`;
    }
    html += board(title, hint, list, lo, hi, g.id, 5);
  });
  $('main').innerHTML = html;
}

/* ---------------- 컨트롤 ---------------- */
document.querySelectorAll('[data-fuel]').forEach((b) => b.addEventListener('click', () => {
  S.fuel = b.dataset.fuel;
  document.querySelectorAll('[data-fuel]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  save(); render();
}));
function bindToggle(id, key) {
  const el = $(id);
  el.setAttribute('aria-pressed', String(S[key]));
  el.addEventListener('click', () => {
    S[key] = !S[key];
    el.setAttribute('aria-pressed', String(S[key]));
    save(); render();
  });
}
bindToggle('tSelf', 'self'); bindToggle('t24', 'h24'); bindToggle('tAlt', 'alt');

const offEl = $('off');
const offLabel = () => { $('offOut').textContent = S.off >= 21 ? '제한 없음' : `${S.off} km`; };
offEl.addEventListener('input', () => { S.off = +offEl.value; offLabel(); save(); render(); });
$('brand').addEventListener('change', (e) => { S.brand = e.target.value; render(); });
$('reg').addEventListener('change', (e) => { S.reg = e.target.value; render(); });
$('vol').addEventListener('input', (e) => { S.vol = Math.max(1, +e.target.value || 40); save(); render(); });
let qt;
$('q').addEventListener('input', (e) => {
  clearTimeout(qt);
  qt = setTimeout(() => { S.q = e.target.value.trim(); render(); }, 180);
});
document.addEventListener('click', (e) => {
  const more = e.target.closest('[data-leg]');
  if (more) {
    S.open[more.dataset.leg] = !S.open[more.dataset.leg];
    render();
    $(`leg-${more.dataset.leg}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    return;
  }
  const go = e.target.closest('[data-goto]');
  if (go) {
    S.focus = go.dataset.goto;
    render();
    $(`leg-${go.dataset.goto}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }
});

/* ---------------- 시작 ---------------- */
document.querySelectorAll('[data-fuel]').forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.fuel === S.fuel)));
offEl.value = S.off; offLabel();
$('vol').value = S.vol;

fetch('/api/config').then((r) => r.json()).then((cfg) => {
  hasTmapKey = cfg.hasTmapKey;
  maxWaypoints = cfg.maxWaypoints ?? 5;
  if (!hasTmapKey) {
    banner('modeBanner', '<b>TMAP_APP_KEY 가 없습니다.</b> 장소 검색이 꺼지고, 경로는 정거장 사이를 직선으로 이은 근사값으로 계산됩니다. '
      + '<code>.env</code> 에 키를 넣고 서버를 다시 시작하면 실제 도로 경로로 조회합니다.');
  }
  renderStops();
}).catch(() => renderStops());
