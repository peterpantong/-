/**
 * 경로 조회 → 경유 시·군·구 판별 → 오피넷 유가 수집 → 구간별 정리.
 */
import { sampleLine } from './geo.js';
import * as tmap from './tmap.js';
import { fetchRegion } from './opinet.js';
import { analyzeRoute, straightLineRoute } from './route.js';
import { annotateStations, orderedRegions } from './stations.js';

/** 역지오코딩 샘플 간격 (km). 촘촘할수록 정확하지만 API 호출이 늘어난다. */
const REGION_SAMPLE_KM = 7;

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i], i);
    }
  }));
  return out;
}

/**
 * @param {{lat:number,lon:number,name:string}} start
 * @param {{lat:number,lon:number,name:string}} goal
 * @param {{lat:number,lon:number,name:string,viaExpressway?:boolean}[]} waypoints
 * @param {{mode?:'tmap'|'straight', key?:string}} options
 */
export async function planRoute({ start, goal, waypoints = [] }, { mode = 'tmap', key } = {}) {
  const warnings = [];

  let analysis;
  if (mode === 'tmap') {
    const geojson = await tmap.route({ start, goal, waypoints, key });
    analysis = analyzeRoute(geojson, { startName: start.name, goalName: goal.name });
  } else {
    analysis = straightLineRoute([start, ...waypoints, goal]);
    warnings.push('TMAP 키 없이 직선 근사 경로로 계산했습니다. 이탈거리는 참고값입니다.');
  }

  // 경로가 지나는 행정구역 알아내기
  const samples = sampleLine(analysis.line, REGION_SAMPLE_KM);
  let regions = [];
  if (mode === 'tmap') {
    const geo = await mapLimit(samples, 4, ([lat, lon]) =>
      tmap.reverseGeocode(lat, lon, { key }).catch(() => null));
    regions = orderedRegions(geo);
  }
  if (!regions.length) {
    throw new Error('경로가 지나는 시·군·구를 확인하지 못했습니다. 출발지/도착지를 다시 지정해 보세요.');
  }

  // 시·군·구별 유가 수집
  const perRegion = await mapLimit(regions, 3, async (r) => {
    try {
      return await fetchRegion(r.sido, r.sigungu);
    } catch (e) {
      warnings.push(`${r.sido} ${r.sigungu} 유가를 가져오지 못했습니다: ${e.message}`);
      return [];
    }
  });

  // 오피넷 응답에는 시·군·구 필드가 없어, 어느 지역 조회로 받아온 건지를 붙여둔다.
  const stations = perRegion.flatMap((list, i) =>
    list.map((st) => ({ ...st, sido: regions[i].sido, region: regions[i].sigungu })));

  const annotated = annotateStations(stations, analysis);
  const usable = annotated.filter((s) => !s.blocked);
  const asOf = usable.map((s) => s.updatedAt).filter(Boolean).sort().pop() || null;

  return {
    route: {
      segments: analysis.segments,
      totalKm: analysis.totalKm,
      totalMin: analysis.totalMin,
      tollFare: analysis.tollFare,
      approximate: Boolean(analysis.approximate),
      line: analysis.line,
    },
    regions,
    stations: annotated,
    counts: { collected: annotated.length, usable: usable.length, blocked: annotated.length - usable.length },
    asOf,
    warnings,
  };
}
