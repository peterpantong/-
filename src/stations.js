/**
 * 주유소를 경로에 붙인다 — 어느 구간에서, 얼마나 벗어나서 들를 수 있는지.
 */
import { nearestOnLine } from './geo.js';

/** 고속도로 휴게소 주유소로 인정할 최대 이격 (km). 본선에서 이 안쪽이면 진행 방향으로 본다. */
export const SERVICE_AREA_MAX_KM = 0.35;

const HIGHWAY_ADDRESS = /고속도로|고속국도/;

/**
 * @param {object[]} stations 오피넷 주유소 목록
 * @param {{line:[number,number][], vertexSegment:number[], segments:object[]}} analysis
 */
export function annotateStations(stations, analysis) {
  const { line, vertexSegment, segments } = analysis;
  const isRoad = (i) => segments[vertexSegment[i]]?.kind === 'road';
  // 선분 한쪽 끝만 일반도로면 그 선분은 이미 고속도로로 넘어가는 중이라 후보에서 뺀다.
  const isRoadSegment = (i) => isRoad(i) && isRoad(i + 1);
  const hasRoadSegment = segments.some((s) => s.kind === 'road');

  return stations.map((st) => {
    const all = nearestOnLine(st.lat, st.lon, line);
    const road = hasRoadSegment ? nearestOnLine(st.lat, st.lon, line, isRoadSegment) : { km: Infinity, index: -1 };
    const onHighway = HIGHWAY_ADDRESS.test(st.address);

    let blocked = '';
    let segment;
    let offRouteKm;
    let serviceArea = false;
    let needsExit = false;

    if (onHighway) {
      // 반대 방향 휴게소와 이 경로가 지나지 않는 노선의 휴게소를 여기서 걸러낸다.
      // 두 방향 휴게소는 본선을 사이에 두고 떨어져 있어, 실제 주행 차선을 따라간
      // 경로선과의 거리로 진행 방향 것만 남는다.
      if (all.km <= SERVICE_AREA_MAX_KM) {
        serviceArea = true;
        segment = vertexSegment[all.index];
        offRouteKm = 0;
      } else {
        blocked = '이 경로에서 진입할 수 없는 고속도로 주유소';
        segment = vertexSegment[all.index];
        offRouteKm = all.km;
      }
    } else if (!hasRoadSegment) {
      blocked = '경로 전체가 고속도로 구간이라 들를 수 없음';
      segment = vertexSegment[all.index];
      offRouteKm = all.km;
    } else {
      segment = vertexSegment[road.index];
      offRouteKm = road.km;
      // 고속도로 본선에 더 가깝다면, 그 구간에서는 IC로 빠져나가야 닿는 곳이다.
      needsExit = all.km < road.km - 0.05;
    }

    return {
      ...st,
      segment,
      offRouteKm: Number(offRouteKm.toFixed(1)),
      serviceArea,
      needsExit,
      blocked,
    };
  });
}

/** 경로가 지나는 시·군·구 목록을 순서대로 (중복 제거) */
export function orderedRegions(samples) {
  const seen = new Set();
  const out = [];
  for (const s of samples) {
    if (!s?.sido || !s?.sigungu) continue;
    const key = `${s.sido}|${s.sigungu}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ sido: s.sido, sigungu: s.sigungu });
  }
  return out;
}
