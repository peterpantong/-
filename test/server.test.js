import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { clearCache } from '../src/opinet.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const opinetHtml = await fs.readFile(path.join(HERE, 'fixtures/opinet-geoje.html'), 'utf8');

/** 실제 TMAP 응답 형태를 본뜬 합성 경로: 거제 시내(일반) → 고속도로 → 거제 시내(일반) */
function tmapRoute() {
  const leg = (lat0, lat1, name, index) => ({
    type: 'Feature',
    geometry: {
      type: 'LineString',
      coordinates: Array.from({ length: 41 }, (_, i) => [128.62, lat0 + (lat1 - lat0) * (i / 40)]),
    },
    properties: { index, name, distance: 5000, time: 300 },
  });
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.62, 34.85] },
        properties: { index: 0, name: '출발', totalDistance: 30000, totalTime: 1800, totalFare: 2400 } },
      leg(34.85, 34.88, '거제대로', 1),
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.62, 34.88] },
        properties: { index: 2, name: '거제IC', description: '거제IC 방면' } },
      leg(34.88, 34.95, '남해고속도로', 3),
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.62, 34.95] },
        properties: { index: 4, name: '사등IC', description: '사등IC 진출' } },
      leg(34.95, 34.99, '거제북로', 5),
    ],
  };
}

let realFetch;
let baseUrl;
let server;

before(async () => {
  process.env.TMAP_APP_KEY = 'test-key';
  realFetch = globalThis.fetch;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('opinet.co.kr') && (init.method || 'GET') === 'GET') {
      return new Response("<script>frm.opinet_key.value = 'TESTTOKEN';</script>", {
        headers: { 'Content-Type': 'text/html', 'Set-Cookie': 'JSESSIONID=abc; Path=/' },
      });
    }
    if (url.includes('opinet.co.kr')) {
      return new Response(opinetHtml, { headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('/tmap/routes')) {
      return new Response(JSON.stringify(tmapRoute()), { headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('reversegeocoding')) {
      return new Response(JSON.stringify({ addressInfo: { city_do: '경상남도', gu_gun: '거제시', eup_myun: '거제면' } }),
        { headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('/tmap/pois')) {
      return new Response(JSON.stringify({ searchPoiInfo: { pois: { poi: [
        { id: '1', name: '거제면사무소', upperAddrName: '경남', middleAddrName: '거제시',
          lowerAddrName: '거제면', frontLat: '34.85106', frontLon: '128.5904' },
      ] } } }), { headers: { 'Content-Type': 'application/json' } });
    }
    throw new Error(`예상하지 못한 요청: ${url}`);
  };
  clearCache();
  ({ server } = await import('../src/server.js'));
  await new Promise((r) => server.listen(0, r));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  globalThis.fetch = realFetch;
  delete process.env.TMAP_APP_KEY;
  await new Promise((r) => server.close(r));
});

const get = async (p) => {
  const res = await realFetch(`${baseUrl}${p}`);
  return { status: res.status, body: await res.json() };
};
const post = async (p, payload) => {
  const res = await realFetch(`${baseUrl}${p}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  return { status: res.status, body: await res.json() };
};

test('GET /api/config 는 키 유무를 알려준다', async () => {
  const { status, body } = await get('/api/config');
  assert.equal(status, 200);
  assert.equal(body.hasTmapKey, true);
  assert.equal(body.maxWaypoints, 5);
});

test('GET /api/poi 는 장소 후보를 좌표와 함께 준다', async () => {
  const { status, body } = await get('/api/poi?q=거제면사무소');
  assert.equal(status, 200);
  assert.equal(body.results[0].name, '거제면사무소');
  assert.ok(Math.abs(body.results[0].lat - 34.85106) < 1e-4);
});

test('GET /api/poi 는 너무 짧은 질의를 거절한다', async () => {
  const { status } = await get('/api/poi?q=거');
  assert.equal(status, 400);
});

test('POST /api/plan 은 구간·주유소·집계를 돌려준다', async () => {
  const { status, body } = await post('/api/plan', {
    start: { lat: 34.85106, lon: 128.5904, name: '거제면사무소' },
    goal: { lat: 34.99, lon: 128.62, name: '도착지' },
  });
  assert.equal(status, 200);
  assert.deepEqual(body.route.segments.map((s) => s.kind), ['road', 'expy', 'road']);
  assert.equal(body.route.segments[1].from, '거제IC');
  assert.equal(body.route.segments[1].to, '사등IC');
  assert.equal(body.route.totalKm, 30);
  assert.equal(body.route.tollFare, 2400);
  assert.deepEqual(body.regions, [{ sido: '경상남도', sigungu: '거제시' }]);
  assert.equal(body.counts.collected, 8);
  assert.ok(body.asOf, '기준 시각이 있어야 한다');

  for (const st of body.stations) {
    assert.ok(Number.isInteger(st.segment) && st.segment >= 0);
    assert.ok(Number.isFinite(st.offRouteKm));
    assert.equal(typeof st.serviceArea, 'boolean');
  }
  // 모든 픽스처 주유소는 일반 시내 주유소라 휴게소로 잡히면 안 된다.
  assert.equal(body.stations.filter((s) => s.serviceArea).length, 0);
});

test('POST /api/plan 은 좌표가 없으면 거절한다', async () => {
  const { status, body } = await post('/api/plan', { start: { name: '어디' }, goal: { lat: 35, lon: 128 } });
  assert.equal(status, 400);
  assert.match(body.error, /출발지 좌표/);
});

test('POST /api/plan 은 국내 범위 밖 좌표를 거절한다', async () => {
  const { status, body } = await post('/api/plan', {
    start: { lat: 48.85, lon: 2.35, name: '파리' }, goal: { lat: 35, lon: 128, name: '어디' },
  });
  assert.equal(status, 400);
  assert.match(body.error, /국내 범위/);
});

test('POST /api/plan 은 경유지 상한을 지킨다', async () => {
  const via = Array.from({ length: 6 }, (_, i) => ({ lat: 34.9 + i * 0.01, lon: 128.6, name: `경유${i}` }));
  const { status, body } = await post('/api/plan', {
    start: { lat: 34.85, lon: 128.59, name: 'a' }, goal: { lat: 34.99, lon: 128.62, name: 'b' }, waypoints: via,
  });
  assert.equal(status, 400);
  assert.match(body.error, /최대 5곳/);
});

test('정적 파일을 서빙하고 디렉터리 밖 접근은 막는다', async () => {
  const page = await realFetch(`${baseUrl}/`);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /루트 최저가 주유소/);
  const escape = await realFetch(`${baseUrl}/../package.json`, { redirect: 'manual' });
  assert.ok(escape.status === 403 || escape.status === 404 || escape.status === 301, `${escape.status}`);
});

test('ACCESS_CODE 를 걸면 코드 없이는 조회할 수 없다', async () => {
  process.env.ACCESS_CODE = '비밀번호';
  try {
    const bare = await realFetch(`${baseUrl}/api/poi?q=거제면사무소`);
    assert.equal(bare.status, 401);
    assert.equal((await bare.json()).code, 'access_code_required');

    const send = (code) => realFetch(`${baseUrl}/api/poi?q=거제면사무소`,
      { headers: { 'x-access-code': encodeURIComponent(code) } });

    assert.equal((await send('틀린값')).status, 401, '길이가 달라도 401');
    assert.equal((await send('비밀번혼')).status, 401, '길이가 같아도 401');
    assert.equal((await send('비밀번호')).status, 200, '한글 코드도 통과해야 한다');
    // 인코딩이 깨진 헤더를 받아도 서버가 죽지 않는다.
    assert.equal((await realFetch(`${baseUrl}/api/poi?q=거제면사무소`,
      { headers: { 'x-access-code': '%E0%A4%A' } })).status, 401);

    // 코드를 몰라도 화면 자체는 열려야 코드 입력창을 띄울 수 있다.
    assert.equal((await realFetch(`${baseUrl}/`)).status, 200);
    const cfg = await (await realFetch(`${baseUrl}/api/config`)).json();
    assert.equal(cfg.needsAccessCode, true, '설정 조회는 코드 없이도 되어야 한다');
  } finally {
    delete process.env.ACCESS_CODE;
  }
});

test('ACCESS_CODE 가 없으면 아무나 조회할 수 있다', async () => {
  const res = await realFetch(`${baseUrl}/api/poi?q=거제면사무소`);
  assert.equal(res.status, 200);
  assert.equal((await (await realFetch(`${baseUrl}/api/config`)).json()).needsAccessCode, false);
});

test('매니페스트와 아이콘을 알맞은 타입으로 내려준다', async () => {
  const m = await realFetch(`${baseUrl}/manifest.webmanifest`);
  assert.equal(m.status, 200);
  assert.match(m.headers.get('content-type'), /manifest\+json/);
  assert.equal((await m.json()).short_name, '주유루트');

  const icon = await realFetch(`${baseUrl}/icons/icon-192.png`);
  assert.equal(icon.status, 200);
  assert.equal(icon.headers.get('content-type'), 'image/png');
});
