/**
 * 루트를 저장하고 링크로 주고받기 위한 직렬화.
 * 브라우저와 테스트 양쪽에서 그대로 쓰도록 의존성 없이 둔다.
 */

/** 국내 좌표 범위. 서버의 검증과 같은 기준. */
const BOUNDS = { latMin: 33, latMax: 39, lonMin: 124, lonMax: 132 };
export const MAX_STOPS = 7;   // 출발 + 경유 5 + 도착

function ok(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= BOUNDS.latMin && lat <= BOUNDS.latMax
    && lon >= BOUNDS.lonMin && lon <= BOUNDS.lonMax;
}

/** 정거장 목록 → URL 쿼리에 넣을 문자열 */
export function encodeRoute(stops) {
  const compact = stops
    .filter((s) => s.picked && ok(s.picked.lat, s.picked.lon))
    .map((s) => ({
      n: String(s.picked.name || '').slice(0, 60),
      y: Number(s.picked.lat.toFixed(5)),
      x: Number(s.picked.lon.toFixed(5)),
    }));
  return compact.length >= 2 ? JSON.stringify(compact) : '';
}

/**
 * 링크나 저장값 → 정거장 목록. 형식이 어긋나면 null.
 * 남이 준 링크도 그대로 들어오므로 좌표와 개수를 모두 확인한다.
 */
export function decodeRoute(text) {
  if (!text) return null;
  let parsed;
  try { parsed = JSON.parse(text); } catch { return null; }
  if (!Array.isArray(parsed) || parsed.length < 2 || parsed.length > MAX_STOPS) return null;

  const stops = [];
  for (const [i, item] of parsed.entries()) {
    const lat = Number(item?.y), lon = Number(item?.x);
    if (!ok(lat, lon)) return null;
    const role = i === 0 ? 'start' : i === parsed.length - 1 ? 'goal' : 'via';
    const name = String(item?.n ?? '').slice(0, 60) || `${lat}, ${lon}`;
    stops.push({
      role,
      label: role === 'start' ? '출발지' : role === 'goal' ? '도착지' : '경유지',
      text: name,
      picked: { name, lat, lon },
    });
  }
  return stops;
}

/** 자동으로 붙는 루트 이름 */
export function routeName(stops) {
  const named = stops.filter((s) => s.picked);
  if (named.length < 2) return '';
  const first = named[0].picked.name;
  const last = named[named.length - 1].picked.name;
  const via = named.length > 2 ? ` (경유 ${named.length - 2})` : '';
  return `${first} → ${last}${via}`;
}

/** 출발지와 도착지를 맞바꾼다 — 돌아오는 길 조회용 */
export function reverseStops(stops) {
  return [...stops].reverse().map((s, i, arr) => ({
    ...s,
    role: i === 0 ? 'start' : i === arr.length - 1 ? 'goal' : 'via',
    label: i === 0 ? '출발지' : i === arr.length - 1 ? '도착지' : '경유지',
  }));
}

/**
 * 최근 조회 목록에 새 항목을 얹는다.
 * 같은 루트를 다시 조회하면 중복으로 쌓이지 않고 맨 앞으로 올라온다.
 */
export function pushRecent(list, entry, limit = 5) {
  if (!entry?.route) return Array.isArray(list) ? list.slice(0, limit) : [];
  const rest = (Array.isArray(list) ? list : []).filter((x) => x?.route && x.route !== entry.route);
  return [entry, ...rest].slice(0, limit);
}
