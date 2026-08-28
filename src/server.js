/**
 * 루트 최저가 주유소 — 로컬 웹 서버.
 * 의존성 없이 Node 표준 모듈만 쓴다. `npm start` 후 http://localhost:3000
 */
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as tmap from './tmap.js';
import { planRoute } from './plan.js';
import { MAX_WAYPOINTS } from './tmap.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PUBLIC = path.join(ROOT, 'public');
const PORT = Number(process.env.PORT || 3000);

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.png': 'image/png',
};

/**
 * 인터넷에 올려 두면 주소를 아는 누구나 TMAP 호출을 일으킬 수 있다.
 * ACCESS_CODE 를 설정하면 그 값을 아는 사람만 조회할 수 있다.
 */
function accessAllowed(req) {
  const expected = process.env.ACCESS_CODE;
  if (!expected) return true;
  const raw = req.headers['x-access-code'];
  if (typeof raw !== 'string') return false;
  // HTTP 헤더는 ASCII 만 담을 수 있어 한글 코드도 쓸 수 있도록 퍼센트 인코딩해 받는다.
  let given;
  try { given = decodeURIComponent(raw); } catch { return false; }
  const a = Buffer.from(given), b = Buffer.from(expected);
  // 길이가 다르면 timingSafeEqual 이 던지므로 먼저 거른다.
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function send(res, status, payload, headers = {}) {
  const body = typeof payload === 'string' || Buffer.isBuffer(payload)
    ? payload : JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    ...headers,
  });
  res.end(body);
}

async function readJson(req, limitBytes = 256 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const c of req) {
    size += c.length;
    if (size > limitBytes) throw new Error('요청이 너무 큽니다.');
    chunks.push(c);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function asStop(v, label) {
  const lat = Number(v?.lat), lon = Number(v?.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) throw new Error(`${label} 좌표가 없습니다.`);
  if (lat < 33 || lat > 39 || lon < 124 || lon > 132) throw new Error(`${label} 좌표가 국내 범위를 벗어났습니다.`);
  return { lat, lon, name: String(v.name || label).slice(0, 60), viaExpressway: Boolean(v.viaExpressway) };
}

async function serveStatic(req, res, urlPath) {
  const rel = urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '');
  const file = path.join(PUBLIC, rel);
  // 디렉터리 밖으로 나가는 경로 차단
  if (!file.startsWith(PUBLIC + path.sep) && file !== path.join(PUBLIC, 'index.html')) {
    return send(res, 403, { error: '접근할 수 없습니다.' });
  }
  try {
    const data = await fs.readFile(file);
    send(res, 200, data, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
  } catch {
    send(res, 404, { error: '찾을 수 없습니다.' });
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  try {
    if (req.method === 'GET' && url.pathname === '/api/config') {
      return send(res, 200, {
        hasTmapKey: tmap.hasKey(),
        maxWaypoints: MAX_WAYPOINTS,
        needsAccessCode: Boolean(process.env.ACCESS_CODE),
      });
    }

    if (url.pathname.startsWith('/api/') && !accessAllowed(req)) {
      return send(res, 401, { error: '접속 코드가 필요합니다.', code: 'access_code_required' });
    }

    if (req.method === 'GET' && url.pathname === '/api/poi') {
      const q = (url.searchParams.get('q') || '').trim();
      if (q.length < 2) return send(res, 400, { error: '두 글자 이상 입력하세요.' });
      if (!tmap.hasKey()) return send(res, 400, { error: 'TMAP_APP_KEY 가 없어 장소 검색을 쓸 수 없습니다. 좌표를 직접 입력하세요.' });
      const { results, diagnostics } = await tmap.searchPoi(q);
      // 결과가 없을 때만 진단을 함께 보낸다 — 왜 비었는지는 응답 원문을 봐야 알 수 있다.
      return send(res, 200, results.length ? { results } : { results, diagnostics });
    }

    if (req.method === 'POST' && url.pathname === '/api/plan') {
      const body = await readJson(req);
      const start = asStop(body.start, '출발지');
      const goal = asStop(body.goal, '도착지');
      const waypoints = (body.waypoints || []).map((w, i) => asStop(w, `경유지 ${i + 1}`));
      const mode = tmap.hasKey() && body.mode !== 'straight' ? 'tmap' : 'straight';
      if (mode === 'tmap' && waypoints.length > MAX_WAYPOINTS) {
        return send(res, 400, { error: `경유지는 최대 ${MAX_WAYPOINTS}곳입니다.` });
      }
      const plan = await planRoute({ start, goal, waypoints }, { mode });
      return send(res, 200, plan);
    }

    if (req.method === 'GET' && url.pathname === '/health') return send(res, 200, { ok: true });

    if (req.method === 'GET') return serveStatic(req, res, url.pathname);
    send(res, 405, { error: '지원하지 않는 요청입니다.' });
  } catch (err) {
    const status = err?.name === 'TmapError' ? 502 : 400;
    send(res, status, { error: err?.message || '알 수 없는 오류', detail: err?.body });
  }
});

if (process.argv[1] && process.argv[1].endsWith('server.js')) {
  server.listen(PORT, () => {
    console.log(`▶ http://localhost:${PORT}`);
    console.log(tmap.hasKey()
      ? '  TMAP_APP_KEY 감지됨 — 실제 도로 경로로 조회합니다.'
      : '  TMAP_APP_KEY 없음 — 직선 근사 모드로 동작합니다. .env 에 키를 넣으면 실제 경로를 씁니다.');
  });
}

export { server };
