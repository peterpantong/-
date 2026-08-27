/**
 * TMAP 경로 응답(GeoJSON) → 주유 관점의 "구간" 분해.
 *
 * 핵심 규칙: 고속도로를 달리는 동안에는 IC로 빠져나가지 않는 한 시내 주유소를 쓸 수 없다.
 * 그래서 경로를 일반도로 구간과 고속도로 구간으로 잘라, 고속도로 구간에서는
 * 진행 방향 휴게소 주유소만 후보로 남긴다.
 */
import { haversine, lineLength } from './geo.js';

const EXPRESSWAY = /고속도로|고속국도/;
const JUNCTION = /(IC|JC|분기점|나들목|요금소|TG|톨게이트|휴게소)/i;
const SEGMENT_IDS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export function isExpresswayName(name) {
  return EXPRESSWAY.test(name || '');
}

/** LineString 피처들을 이어붙여 하나의 폴리라인으로 만든다. */
function collectVertices(features) {
  const lines = features
    .filter((f) => f?.geometry?.type === 'LineString')
    .map((f, i) => ({ f, order: Number(f.properties?.index ?? i), i }))
    .sort((a, b) => (a.order - b.order) || (a.i - b.i))
    .map((x) => x.f);

  const vertices = [];
  for (const f of lines) {
    const road = f.properties?.name || '';
    const expy = isExpresswayName(road);
    for (const [lon, lat] of f.geometry.coordinates) {
      const prev = vertices[vertices.length - 1];
      // 연속한 피처는 끝점을 공유한다. 같은 점이 두 번 들어가면 길이가 부풀지는 않지만
      // 구간 경계 판정이 흔들려서 걸러낸다.
      if (prev && prev.lat === lat && prev.lon === lon) {
        if (!prev.road && road) { prev.road = road; prev.expy = expy; }
        continue;
      }
      vertices.push({ lat, lon, road, expy });
    }
  }
  return vertices;
}

/** 회전안내 지점 중 IC·JC·휴게소처럼 구간 경계를 부를 만한 이름을 뽑는다. */
function collectLandmarks(features) {
  return features
    .filter((f) => f?.geometry?.type === 'Point')
    .map((f) => {
      const p = f.properties || {};
      const label = [p.name, p.description].find((t) => t && JUNCTION.test(t)) || '';
      const [lon, lat] = f.geometry.coordinates;
      return label ? { lat, lon, label: label.trim() } : null;
    })
    .filter(Boolean);
}

/** 정점별 누적 주행거리 */
function cumulative(line) {
  const cum = [0];
  for (let i = 1; i < line.length; i++) {
    cum.push(cum[i - 1] + haversine(line[i - 1][0], line[i - 1][1], line[i][0], line[i][1]));
  }
  return cum;
}

/**
 * 구간 경계에 이름을 붙인다.
 * 직선거리 대신 "경로를 따라간 거리"로 재야 한다 — 나들목 진출입 램프에서는
 * 경로가 크게 돌아 나가서 직선거리로는 엉뚱한 지점이 더 가까워 보인다.
 */
function labelAt(landmarks, cum, index, windowKm = 3) {
  let best = null;
  for (const lm of landmarks) {
    const along = Math.abs(cum[lm.vertex] - cum[index]);
    // 정점 간격이 성긴 경로에서도 경계 바로 앞뒤의 지점은 놓치지 않는다.
    const adjacent = Math.abs(lm.vertex - index) <= 1;
    if ((along <= windowKm || adjacent) && (!best || along < best.along)) best = { ...lm, along };
  }
  return best;
}

/**
 * @param {object} geojson TMAP /tmap/routes 응답
 * @returns {{line:[number,number][], vertexSegment:number[], segments:object[], totalKm:number, totalMin:number, tollFare:number|null}}
 */
export function analyzeRoute(geojson, { startName = '출발지', goalName = '도착지' } = {}) {
  const features = geojson?.features;
  if (!Array.isArray(features) || !features.length) {
    throw new Error('경로 응답에 구간 정보가 없습니다.');
  }
  const vertices = collectVertices(features);
  if (vertices.length < 2) throw new Error('경로 좌표가 부족합니다.');

  const landmarks = collectLandmarks(features);
  const summary = features.find((f) => f.properties?.totalDistance != null)?.properties ?? {};

  // 고속도로 여부가 바뀌는 지점에서 구간을 자른다.
  const runs = [];
  let cur = { start: 0, expy: vertices[0].expy, roads: new Set([vertices[0].road].filter(Boolean)) };
  for (let i = 1; i < vertices.length; i++) {
    if (vertices[i].expy !== cur.expy) {
      cur.end = i;
      runs.push(cur);
      cur = { start: i, expy: vertices[i].expy, roads: new Set() };
    }
    if (vertices[i].road) cur.roads.add(vertices[i].road);
  }
  cur.end = vertices.length - 1;
  runs.push(cur);

  // 아주 짧은 구간(진출입 램프 등)은 앞 구간에 흡수시켜 목록이 잘게 쪼개지지 않게 한다.
  const merged = [];
  for (const run of runs) {
    const km = lineLength(vertices.slice(run.start, run.end + 1).map((v) => [v.lat, v.lon]));
    const last = merged[merged.length - 1];
    if (km < 1.5 && last) {
      last.end = run.end;
      for (const r of run.roads) last.roads.add(r);
    } else {
      merged.push({ ...run, km });
    }
  }
  // 흡수 후 같은 종류가 이웃하면 합친다.
  const runsFinal = [];
  for (const run of merged) {
    const last = runsFinal[runsFinal.length - 1];
    if (last && last.expy === run.expy) {
      last.end = run.end;
      for (const r of run.roads) last.roads.add(r);
    } else {
      runsFinal.push(run);
    }
  }

  const line = vertices.map((v) => [v.lat, v.lon]);
  const cum = cumulative(line);
  for (const lm of landmarks) {
    let best = { km: Infinity, i: 0 };
    for (let i = 0; i < line.length; i++) {
      const km = haversine(lm.lat, lm.lon, line[i][0], line[i][1]);
      if (km < best.km) best = { km, i };
    }
    lm.vertex = best.i;
  }
  const vertexSegment = new Array(vertices.length).fill(0);
  const segments = runsFinal.map((run, idx) => {
    for (let i = run.start; i <= run.end; i++) vertexSegment[i] = idx;
    const slice = line.slice(run.start, run.end + 1);
    const from = idx === 0 ? startName
      : (labelAt(landmarks, cum, run.start)?.label || '구간 시작');
    const to = idx === runsFinal.length - 1 ? goalName
      : (labelAt(landmarks, cum, run.end)?.label || '구간 끝');
    const roads = [...run.roads].filter(Boolean);
    return {
      id: SEGMENT_IDS[idx] || String(idx + 1),
      kind: run.expy ? 'expy' : 'road',
      from, to,
      name: `${from} → ${to}`,
      roads,
      roadLabel: roads.slice(0, 3).join(' · ') || (run.expy ? '고속도로' : '일반도로'),
      lengthKm: Number(lineLength(slice).toFixed(1)),
      startIndex: run.start,
      endIndex: run.end,
    };
  });

  const totalKm = Number((summary.totalDistance != null
    ? summary.totalDistance / 1000
    : lineLength(line)).toFixed(1));

  return {
    line,
    vertexSegment,
    segments,
    totalKm,
    totalMin: summary.totalTime != null ? Math.round(summary.totalTime / 60) : null,
    tollFare: summary.totalFare ?? null,
    fuelFare: summary.taxiFare ?? null,
  };
}

/**
 * 좌표 목록만으로 구간을 만든다 (TMAP 키가 없을 때의 대체 경로).
 * 실제 도로를 따르지 않는 직선 근사이므로 이탈거리는 참고값이다.
 * @param {{lat:number,lon:number,name:string,expressway?:boolean}[]} stops
 */
export function straightLineRoute(stops) {
  if (stops.length < 2) throw new Error('출발지와 도착지가 필요합니다.');
  const line = [];
  const vertexSegment = [];
  const segments = [];

  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i], b = stops[i + 1];
    // 각 정거장의 viaExpressway 는 "직전 정거장에서 여기까지를 고속도로로 달린다"는 표시다.
    const expy = Boolean(b.viaExpressway);
    const startIndex = line.length;
    const km = haversine(a.lat, a.lon, b.lat, b.lon);
    const steps = Math.max(1, Math.round(km / 1.5));
    for (let s = 0; s < steps; s++) {
      const t = s / steps;
      line.push([a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t]);
      vertexSegment.push(i);
    }
    if (i === stops.length - 2) { line.push([b.lat, b.lon]); vertexSegment.push(i); }
    segments.push({
      id: SEGMENT_IDS[i] || String(i + 1),
      kind: expy ? 'expy' : 'road',
      from: a.name, to: b.name, name: `${a.name} → ${b.name}`,
      roads: [], roadLabel: expy ? '고속도로 (직선 근사)' : '직선 근사',
      lengthKm: Number(km.toFixed(1)),
      startIndex, endIndex: line.length - 1,
    });
  }
  return {
    line, vertexSegment, segments,
    totalKm: Number(lineLength(line).toFixed(1)),
    totalMin: null, tollFare: null, fuelFare: null,
    approximate: true,
  };
}
