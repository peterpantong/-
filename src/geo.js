/**
 * 좌표 변환 · 거리 계산.
 *
 * 오피넷은 주유소 좌표를 KATEC(TM128, Bessel 1841 타원체)으로 내려주고,
 * TMAP은 WGS84를 쓴다. 둘을 한 좌표계에서 비교해야 "루트에서 몇 km 떨어졌나"를 잴 수 있다.
 */

const KATEC = {
  a: 6377397.155,          // Bessel 1841
  f: 1 / 299.1528128,
  lat0: 38 * Math.PI / 180,
  lon0: 128 * Math.PI / 180,
  k0: 0.9999,
  x0: 400000,
  y0: 600000,
  // proj4 +towgs84 (position vector 규약): dx, dy, dz, rx", ry", rz", ppm
  towgs84: [-115.80, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43],
};

const WGS84 = { a: 6378137.0, f: 1 / 298.257223563 };

const SEC_TO_RAD = Math.PI / (180 * 3600);

function meridionalArc(phi, a, e2) {
  const e4 = e2 * e2, e6 = e4 * e2;
  return a * (
    (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
    - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi)
    + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi)
    - (35 * e6 / 3072) * Math.sin(6 * phi)
  );
}

/** 횡메르카토르 역변환 → 해당 타원체상의 위/경도(라디안) */
function inverseTM(x, y, datum) {
  const { a, f, lat0, lon0, k0, x0, y0 } = datum;
  const e2 = 2 * f - f * f;
  const ep2 = e2 / (1 - e2);
  const e4 = e2 * e2, e6 = e4 * e2;

  const M = (y - y0) / k0 + meridionalArc(lat0, a, e2);
  const mu = M / (a * (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const e1_2 = e1 * e1, e1_3 = e1_2 * e1, e1_4 = e1_3 * e1;

  const phi1 = mu
    + (3 * e1 / 2 - 27 * e1_3 / 32) * Math.sin(2 * mu)
    + (21 * e1_2 / 16 - 55 * e1_4 / 32) * Math.sin(4 * mu)
    + (151 * e1_3 / 96) * Math.sin(6 * mu)
    + (1097 * e1_4 / 512) * Math.sin(8 * mu);

  const sinP = Math.sin(phi1), cosP = Math.cos(phi1), tanP = Math.tan(phi1);
  const C1 = ep2 * cosP * cosP;
  const T1 = tanP * tanP;
  const N1 = a / Math.sqrt(1 - e2 * sinP * sinP);
  const R1 = a * (1 - e2) / Math.pow(1 - e2 * sinP * sinP, 1.5);
  const D = (x - x0) / (N1 * k0);
  const D2 = D * D, D3 = D2 * D, D4 = D3 * D, D5 = D4 * D, D6 = D5 * D;

  const lat = phi1 - (N1 * tanP / R1) * (
    D2 / 2
    - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D6 / 720
  );
  const lon = lon0 + (
    D
    - (1 + 2 * T1 + C1) * D3 / 6
    + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D5 / 120
  ) / cosP;

  return [lat, lon];
}

function geodeticToGeocentric(lat, lon, h, a, f) {
  const e2 = 2 * f - f * f;
  const sinLat = Math.sin(lat), cosLat = Math.cos(lat);
  const N = a / Math.sqrt(1 - e2 * sinLat * sinLat);
  return [
    (N + h) * cosLat * Math.cos(lon),
    (N + h) * cosLat * Math.sin(lon),
    (N * (1 - e2) + h) * sinLat,
  ];
}

function geocentricToGeodetic(X, Y, Z, a, f) {
  const e2 = 2 * f - f * f;
  const p = Math.hypot(X, Y);
  let lat = Math.atan2(Z, p * (1 - e2));
  // 반복 수렴 — 지표 근처에서 3~4회면 mm 이하로 수렴한다.
  for (let i = 0; i < 6; i++) {
    const sinLat = Math.sin(lat);
    const N = a / Math.sqrt(1 - e2 * sinLat * sinLat);
    const h = p / Math.cos(lat) - N;
    lat = Math.atan2(Z, p * (1 - e2 * N / (N + h)));
  }
  return [lat, Math.atan2(Y, X)];
}

/** Bursa-Wolf 7-parameter (position vector) 변환 */
function helmert([X, Y, Z], [dx, dy, dz, rxSec, rySec, rzSec, ppm]) {
  const rx = rxSec * SEC_TO_RAD, ry = rySec * SEC_TO_RAD, rz = rzSec * SEC_TO_RAD;
  const s = 1 + ppm * 1e-6;
  return [
    dx + s * (X - rz * Y + ry * Z),
    dy + s * (rz * X + Y - rx * Z),
    dz + s * (-ry * X + rx * Y + Z),
  ];
}

/** 오피넷 KATEC 좌표 → WGS84 [위도, 경도] */
export function katecToWgs84(x, y) {
  const [latB, lonB] = inverseTM(x, y, KATEC);
  const xyz = geodeticToGeocentric(latB, lonB, 0, KATEC.a, KATEC.f);
  const [lat, lon] = geocentricToGeodetic(...helmert(xyz, KATEC.towgs84), WGS84.a, WGS84.f);
  return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}

/** UTMK(EPSG:5179, GRS80) — 오피넷 지오코딩 응답이 쓰는 좌표계 */
const UTMK = {
  a: 6378137.0,
  f: 1 / 298.257222101,   // GRS80. WGS84 와의 차이는 지표에서 1mm 미만이라 데이텀 변환이 필요 없다.
  lat0: 38 * Math.PI / 180,
  lon0: 127.5 * Math.PI / 180,
  k0: 0.9996,
  x0: 1000000,
  y0: 2000000,
};

/** UTMK 좌표 → WGS84 [위도, 경도] */
export function utmkToWgs84(x, y) {
  const [lat, lon] = inverseTM(x, y, UTMK);
  return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}

const R_EARTH = 6371.0088;
const D2R = Math.PI / 180;

/** 두 지점 사이 대권거리(km) */
export function haversine(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * D2R, dLon = (lon2 - lon1) * D2R;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * D2R) * Math.cos(lat2 * D2R) * Math.sin(dLon / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.sqrt(h));
}

/**
 * 점에서 선분까지의 최단거리(km).
 * 한 루트 안에서만 쓰므로 위도 보정을 건 평면 근사로 충분하다.
 */
export function distanceToSegment(lat, lon, aLat, aLon, bLat, bLon) {
  const kx = Math.cos(lat * D2R) * 111.32, ky = 110.574;
  const px = (lon - aLon) * kx, py = (lat - aLat) * ky;
  const vx = (bLon - aLon) * kx, vy = (bLat - aLat) * ky;
  const len2 = vx * vx + vy * vy;
  if (len2 === 0) return Math.hypot(px, py);
  const t = Math.max(0, Math.min(1, (px * vx + py * vy) / len2));
  return Math.hypot(px - t * vx, py - t * vy);
}

/**
 * 점에서 폴리라인까지의 최단거리와 그 지점의 정점 인덱스.
 * @param {[number,number][]} line [위도, 경도] 배열
 */
export function nearestOnLine(lat, lon, line, filter) {
  let best = { km: Infinity, index: -1 };
  for (let i = 0; i < line.length - 1; i++) {
    if (filter && !filter(i)) continue;
    const km = distanceToSegment(lat, lon, line[i][0], line[i][1], line[i + 1][0], line[i + 1][1]);
    if (km < best.km) best = { km, index: i };
  }
  return best;
}

/** 폴리라인 총 길이(km) */
export function lineLength(line) {
  let sum = 0;
  for (let i = 0; i < line.length - 1; i++) {
    sum += haversine(line[i][0], line[i][1], line[i + 1][0], line[i + 1][1]);
  }
  return sum;
}

/** 폴리라인을 stepKm 간격으로 샘플링 (역지오코딩 호출 수를 줄이기 위해 씀) */
export function sampleLine(line, stepKm) {
  if (!line.length) return [];
  const out = [line[0]];
  let acc = 0;
  for (let i = 0; i < line.length - 1; i++) {
    acc += haversine(line[i][0], line[i][1], line[i + 1][0], line[i + 1][1]);
    if (acc >= stepKm) { out.push(line[i + 1]); acc = 0; }
  }
  const last = line[line.length - 1];
  if (out[out.length - 1] !== last) out.push(last);
  return out;
}
