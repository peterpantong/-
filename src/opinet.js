/**
 * 오피넷(한국석유공사) 유가 조회.
 *
 * 공개 API 키가 없어도 되도록, 오피넷 웹의 "싼 주유소 찾기" 지역검색을
 * 그대로 호출해 응답 페이지에 심어진 주유소 변수 블록을 읽는다.
 */
import { katecToWgs84, utmkToWgs84 } from './geo.js';

const BASE = 'https://www.opinet.co.kr';
const ENTRY = `${BASE}/searRgSelect.do`;
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

/** 유종 코드 → 응답 변수명 */
export const FUEL_FIELDS = {
  gasoline: 'B027_P',   // 보통휘발유
  premium: 'B034_P',    // 고급휘발유
  diesel: 'D047_P',     // 자동차용 경유
  kerosene: 'C004_P',   // 실내등유
  lpg: 'K015_P',
};

const BRANDS = {
  SKE: 'SK에너지', GSC: 'GS칼텍스', HDO: 'HD현대오일뱅크', SOL: 'S-OIL',
  RTO: '자영알뜰', RTX: '고속도로휴게소', NHO: '농협알뜰', ETC: '자가상표',
  E1G: 'E1', SKG: 'SK가스', NCO: 'NC',
};

const FIELDS = [
  'B027_P', 'B034_P', 'D047_P', 'C004_P', 'K015_P', 'B027_DT', 'D047_DT',
  'OS_NM', 'POLL_DIV_CD', 'POLL_DIV_NM', 'RD_ADDR', 'SELF_DIV_CD', 'SEL24_YN',
  'PHN_NO', 'UNI_ID', 'GIS_X_COOR', 'GIS_Y_COOR', 'CWSH_YN', 'MAINT_YN', 'CVS_YN',
];

/** 가격 문자열 정리. 99999 는 "미판매/정보없음" 자리표시자다. */
function toPrice(raw) {
  const n = Number.parseInt(raw, 10);
  return Number.isInteger(n) && n > 0 && n < 10000 ? n : null;
}

function pickVar(block, name) {
  const m = block.match(new RegExp(`var ${name}\\s*=\\s*"([^"]*)"`));
  return m ? m[1].trim() : '';
}

function parseStations(html) {
  // 오피넷은 주유소마다 var B027_P 로 시작하는 블록을 하나씩 찍어준다.
  const blocks = html.split(/\n(?=[ \t]*var B027_P)/).slice(1);
  const out = [];
  for (const block of blocks) {
    const rec = {};
    for (const f of FIELDS) rec[f] = pickVar(block, f);
    if (!rec.OS_NM) continue;

    const x = Number.parseFloat(rec.GIS_X_COOR);
    const y = Number.parseFloat(rec.GIS_Y_COOR);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const [lat, lon] = katecToWgs84(x, y);

    out.push({
      id: rec.UNI_ID,
      name: rec.OS_NM,
      brand: BRANDS[rec.POLL_DIV_CD] || rec.POLL_DIV_NM || rec.POLL_DIV_CD,
      brandCode: rec.POLL_DIV_CD,
      address: rec.RD_ADDR,
      phone: rec.PHN_NO,
      self: rec.SELF_DIV_CD === 'Y',
      open24h: rec.SEL24_YN === 'Y',
      carWash: rec.CWSH_YN === 'Y',
      maintenance: rec.MAINT_YN === 'Y',
      convenience: rec.CVS_YN === 'Y',
      prices: {
        gasoline: toPrice(rec.B027_P), premium: toPrice(rec.B034_P),
        diesel: toPrice(rec.D047_P), kerosene: toPrice(rec.C004_P), lpg: toPrice(rec.K015_P),
      },
      updatedAt: (rec.B027_DT || rec.D047_DT).slice(0, 16),
      lat: Number(lat.toFixed(5)),
      lon: Number(lon.toFixed(5)),
    });
  }
  return out;
}

function cookieHeader(res, prev = '') {
  const set = res.headers.getSetCookie?.() ?? [];
  const jar = new Map();
  for (const part of prev.split('; ')) {
    const [k, v] = part.split('=');
    if (k) jar.set(k, v);
  }
  for (const c of set) {
    const [k, v] = c.split(';')[0].split('=');
    if (k) jar.set(k, v);
  }
  return [...jar].map(([k, v]) => `${k}=${v}`).join('; ');
}

let session = null;   // { cookie, key, at }
const SESSION_TTL = 10 * 60 * 1000;

/** 진입 페이지에서 세션 쿠키와 폼 토큰(opinet_key)을 받아둔다. */
async function openSession() {
  if (session && Date.now() - session.at < SESSION_TTL) return session;
  const res = await fetch(ENTRY, { headers: { 'User-Agent': UA } });
  const html = await res.text();
  const m = html.match(/opinet_key\.value\s*=\s*'([^']+)'/);
  if (!m) throw new Error('오피넷 진입 페이지에서 폼 토큰을 찾지 못했습니다. 사이트 구조가 바뀌었을 수 있습니다.');
  session = { cookie: cookieHeader(res), key: m[1], at: Date.now() };
  return session;
}

const cache = new Map();    // "시도|시군구" → { at, stations }
const CACHE_TTL = 20 * 60 * 1000;

/**
 * 한 시·군·구의 주유소 전체를 가져온다.
 * @param {string} sido 예: "경상남도", "부산광역시"
 * @param {string} sigungu 예: "거제시", "해운대구"
 */
export async function fetchRegion(sido, sigungu, { force = false } = {}) {
  const key = `${sido}|${sigungu}`;
  const hit = cache.get(key);
  if (!force && hit && Date.now() - hit.at < CACHE_TTL) return hit.stations;

  const s = await openSession();
  const body = new URLSearchParams({
    SEARCH_MOD: '1', SIDO_NM: sido, SIGUNGU_NM: sigungu,
    opinet_key: s.key, netfunnel_key: 'nf',
  });
  const res = await fetch(ENTRY, {
    method: 'POST',
    headers: {
      'User-Agent': UA, Referer: ENTRY, Cookie: s.cookie,
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    },
    body,
  });
  if (!res.ok) throw new Error(`오피넷 응답 오류 ${res.status} (${sido} ${sigungu})`);
  const html = await res.text();

  // 지역명이 안 먹으면 오피넷이 기본 지역(종로구)을 돌려준다 — 잘못된 데이터를 섞지 않도록 거른다.
  const stations = parseStations(html).filter((st) => st.address.includes(sigungu));
  cache.set(key, { at: Date.now(), stations });
  return stations;
}

/** 시·도 / 시·군·구 / 읍면동 이름을 좌표로. 오프라인 대체 경로에서 쓴다. */
export async function geocode(sido, sigungu = '', dong = '') {
  const res = await fetch(`${BASE}/common/geocodeUtmkSelect.do`, {
    method: 'POST',
    headers: {
      'User-Agent': UA, Referer: ENTRY,
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    },
    body: new URLSearchParams({ sido, sigun: sigungu, dong }),
  });
  const data = await res.json();
  const hit = data?.result?.[0];
  if (!hit) return null;
  // 주유소 좌표(KATEC)와 달리 이 응답만 UTMK(EPSG:5179)다.
  const [lat, lon] = utmkToWgs84(hit.GIS_X, hit.GIS_Y);
  return { lat: Number(lat.toFixed(5)), lon: Number(lon.toFixed(5)) };
}

export function clearCache() { cache.clear(); session = null; }
export const _internal = { parseStations, toPrice };
