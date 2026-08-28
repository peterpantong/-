/**
 * TMAP(SK오픈API) 클라이언트 — 장소 검색 · 자동차 경로 · 역지오코딩.
 *
 * appKey 는 https://openapi.sk.com 에서 발급받아 TMAP_APP_KEY 환경변수로 넣는다.
 */

const HOST = 'https://apis.openapi.sk.com';
export const MAX_WAYPOINTS = 5;      // TMAP 일반 경로안내의 경유지 상한

export class TmapError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = 'TmapError';
    this.status = status;
    this.body = body;
  }
}

function appKey(key) {
  const k = key || process.env.TMAP_APP_KEY;
  if (!k) throw new TmapError('TMAP_APP_KEY 가 설정되지 않았습니다. .env 에 키를 넣고 서버를 다시 시작하세요.');
  return k;
}

async function call(url, { method = 'GET', body, key } = {}) {
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: {
        appKey: appKey(key),
        Accept: 'application/json',
        ...(body ? { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' } : {}),
      },
      body,
    });
  } catch (cause) {
    throw new TmapError(`TMAP 서버에 연결하지 못했습니다: ${cause.message}`, { body: String(cause) });
  }
  const text = await res.text();
  if (!res.ok) {
    // TMAP 은 오류를 { error: { message, code } } 로 준다. 원문을 그대로 올려 진단할 수 있게 한다.
    let detail = text.slice(0, 400);
    try { detail = JSON.parse(text)?.error?.message ?? detail; } catch { /* 원문 유지 */ }
    throw new TmapError(`TMAP ${res.status}: ${detail}`, { status: res.status, body: text.slice(0, 2000) });
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new TmapError('TMAP 응답을 JSON 으로 읽지 못했습니다.', { body: text.slice(0, 500) });
  }
  // SK 게이트웨이는 오류를 200 으로 내려보내면서 본문에만 담아 주기도 한다.
  // 그대로 두면 "결과 0건"으로 잘못 읽히므로 여기서 실패로 돌린다.
  const err = data?.error ?? data?.Fault?.faultstring ?? null;
  if (err) {
    const msg = typeof err === 'string' ? err : (err.message || err.code || JSON.stringify(err).slice(0, 200));
    throw new TmapError(`TMAP: ${msg}`, { status: res.status, body: text.slice(0, 2000) });
  }
  return { data, raw: text };
}

/** 장소/주소 검색. 사용자가 입력한 지명을 좌표로 바꾼다. */
export async function searchPoi(keyword, { count = 8, key } = {}) {
  const qs = new URLSearchParams({
    version: '1', searchKeyword: keyword, resCoordType: 'WGS84GEO',
    searchType: 'all', count: String(count), page: '1',
  });
  const { data, raw } = await call(`${HOST}/tmap/pois?${qs}`, { key });
  const pois = data?.searchPoiInfo?.pois?.poi ?? [];
  const results = pois.map((p) => ({
    id: p.id,
    name: p.name,
    address: [p.upperAddrName, p.middleAddrName, p.lowerAddrName, p.detailAddrname, p.firstNo]
      .filter(Boolean).join(' '),
    roadAddress: [p.upperAddrName, p.middleAddrName, p.roadName, p.firstBuildNo].filter(Boolean).join(' '),
    // frontLat/frontLon 은 차량이 실제로 진입하는 지점이라 경로 기점으로 더 정확하다.
    lat: Number(p.frontLat ?? p.noorLat ?? p.lat),
    lon: Number(p.frontLon ?? p.noorLon ?? p.lon),
  }));
  const usable = results.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));
  return {
    results: usable,
    // 결과가 비었을 때 왜 비었는지 알 수 있도록 응답의 앞부분을 남긴다.
    diagnostics: {
      url: `${HOST}/tmap/pois?${qs}`,
      totalCount: data?.searchPoiInfo?.totalCount ?? null,
      parsed: pois.length,
      dropped: results.length - usable.length,
      raw: raw.slice(0, 1200),
    },
  };
}

/**
 * 자동차 경로. 경유지는 최대 5곳.
 * @param {{lat:number,lon:number,name?:string}} start
 * @param {{lat:number,lon:number,name?:string}} goal
 * @param {{lat:number,lon:number,name?:string}[]} waypoints
 */
export async function route({ start, goal, waypoints = [], searchOption = '0', key } = {}) {
  if (waypoints.length > MAX_WAYPOINTS) {
    throw new TmapError(`경유지는 최대 ${MAX_WAYPOINTS}곳까지만 넣을 수 있습니다 (요청 ${waypoints.length}곳).`);
  }
  const form = new URLSearchParams({
    startX: String(start.lon), startY: String(start.lat),
    endX: String(goal.lon), endY: String(goal.lat),
    reqCoordType: 'WGS84GEO', resCoordType: 'WGS84GEO',
    searchOption, trafficInfo: 'N',
    startName: encodeURIComponent(start.name || '출발'),
    endName: encodeURIComponent(goal.name || '도착'),
  });
  if (waypoints.length) {
    form.set('passList', waypoints.map((w) => `${w.lon},${w.lat}`).join('_'));
  }
  const { data } = await call(`${HOST}/tmap/routes?version=1&format=json`, { method: 'POST', body: form, key });
  return data;
}

/** 좌표 → 행정구역. 루트가 어느 시·군·구를 지나는지 알아내는 데 쓴다. */
export async function reverseGeocode(lat, lon, { key } = {}) {
  const qs = new URLSearchParams({
    version: '1', lat: String(lat), lon: String(lon),
    coordType: 'WGS84GEO', addressType: 'A10',
  });
  const { data } = await call(`${HOST}/tmap/geo/reversegeocoding?${qs}`, { key });
  const a = data?.addressInfo;
  if (!a) return null;
  return {
    sido: a.city_do || '',
    sigungu: a.gu_gun || '',
    eupmyeondong: a.eup_myun || a.legalDong || '',
    full: a.fullAddress || '',
  };
}

export function hasKey(key) {
  return Boolean(key || process.env.TMAP_APP_KEY);
}
