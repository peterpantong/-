import assert from 'node:assert/strict';
import { test } from 'node:test';
import { analyzeRoute, straightLineRoute, isExpresswayName } from '../src/route.js';
import { annotateStations, SERVICE_AREA_MAX_KM } from '../src/stations.js';

/**
 * TMAP 응답 형태를 본뜬 합성 픽스처.
 * 일반도로 → 고속도로 → 일반도로 로 이어지는 남북 방향 경로다.
 */
function fixture() {
  const seg = (lat0, lat1, name, index) => ({
    type: 'Feature',
    geometry: {
      type: 'LineString',
      // 실제 TMAP 응답처럼 촘촘하게 (약 250m 간격)
      coordinates: Array.from({ length: 41 }, (_, i) => [128.0, lat0 + (lat1 - lat0) * (i / 40)]),
    },
    properties: { index, name, distance: 1000, time: 60 },
  });
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.0, 35.0] },
        properties: { index: 0, name: '출발', description: '출발지', totalDistance: 66600, totalTime: 3600, totalFare: 4500 } },
      seg(35.0, 35.1, '7번국도', 1),
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.0, 35.1] },
        properties: { index: 2, name: '남산IC', description: '남산IC 진입' } },
      seg(35.1, 35.5, '중부내륙고속도로', 3),
      { type: 'Feature', geometry: { type: 'Point', coordinates: [128.0, 35.5] },
        properties: { index: 4, name: '북산IC', description: '북산IC 진출' } },
      seg(35.5, 35.6, '33번국도', 5),
    ],
  };
}

test('analyzeRoute 는 고속도로 구간을 분리한다', () => {
  const r = analyzeRoute(fixture(), { startName: '집', goalName: '역' });
  assert.equal(r.segments.length, 3);
  assert.deepEqual(r.segments.map((s) => s.kind), ['road', 'expy', 'road']);
  assert.equal(r.segments[0].from, '집');
  assert.equal(r.segments[2].to, '역');
  assert.equal(r.segments[1].from, '남산IC');
  assert.equal(r.segments[1].to, '북산IC');
  assert.deepEqual(r.segments.map((s) => s.id), ['A', 'B', 'C']);
  assert.equal(r.totalKm, 66.6);
  assert.equal(r.totalMin, 60);
  assert.equal(r.tollFare, 4500);
});

test('analyzeRoute 는 모든 정점에 구간 번호를 매긴다', () => {
  const r = analyzeRoute(fixture());
  assert.equal(r.line.length, r.vertexSegment.length);
  assert.ok(r.vertexSegment.every((v) => v >= 0 && v < r.segments.length));
});

test('isExpresswayName', () => {
  assert.ok(isExpresswayName('중부내륙고속도로'));
  assert.ok(isExpresswayName('통영대전고속도로'));
  assert.ok(!isExpresswayName('33번국도'));
  assert.ok(!isExpresswayName(''));
});

test('고속도로 구간의 시내 주유소는 IC로 나가야 하는 곳으로 표시된다', () => {
  const r = analyzeRoute(fixture());
  const [st] = annotateStations([{
    name: '고속도로변 시내주유소', address: '경북 어딘가 시내로 1',
    lat: 35.3, lon: 128.002, prices: { gasoline: 1700 },
  }], r);
  assert.equal(st.blocked, '');
  assert.ok(st.needsExit, '고속도로 본선 옆이면 needsExit');
  // 일반도로 구간(35.0~35.1, 35.5~35.6)까지의 거리로 이탈거리를 잰다.
  assert.ok(st.offRouteKm > 20, `${st.offRouteKm}`);
});

test('진행 방향 휴게소만 남고 반대편 휴게소는 제외된다', () => {
  const r = analyzeRoute(fixture());
  const [onRoute, offRoute] = annotateStations([
    { name: '아무개(북행)휴게소', address: '경북 아무개군 중부내륙고속도로 100',
      lat: 35.3, lon: 128.0008, prices: { gasoline: 1800 } },   // 본선에서 약 70m
    { name: '아무개(남행)휴게소', address: '경북 아무개군 중부내륙고속도로 99',
      lat: 35.3, lon: 128.02, prices: { gasoline: 1800 } },     // 본선에서 약 1.8km
  ], r);
  assert.ok(onRoute.serviceArea, '가까운 쪽은 휴게소로 인정');
  assert.equal(onRoute.offRouteKm, 0);
  assert.equal(onRoute.blocked, '');
  assert.ok(!offRoute.serviceArea);
  assert.match(offRoute.blocked, /진입할 수 없는/);
});

test('SERVICE_AREA_MAX_KM 경계값', () => {
  const r = analyzeRoute(fixture());
  const mk = (lon) => annotateStations([{
    name: 'x', address: '경북 x 중부내륙고속도로 1', lat: 35.3, lon, prices: { gasoline: 1 },
  }], r)[0];
  assert.ok(mk(128.0 + 0.002).serviceArea);          // 약 180m
  assert.ok(!mk(128.0 + 0.01).serviceArea);          // 약 900m
  assert.ok(SERVICE_AREA_MAX_KM > 0.1 && SERVICE_AREA_MAX_KM < 1);
});

test('straightLineRoute 는 경유지 사이마다 구간을 만든다', () => {
  const r = straightLineRoute([
    { lat: 35.0, lon: 128.0, name: '출발' },
    { lat: 35.2, lon: 128.1, name: '경유', viaExpressway: true },
    { lat: 35.5, lon: 128.3, name: '도착' },
  ]);
  assert.equal(r.segments.length, 2);
  // viaExpressway 는 "직전 정거장에서 여기까지" 를 뜻한다.
  assert.equal(r.segments[0].kind, 'expy');
  assert.equal(r.segments[1].kind, 'road');
  assert.ok(r.approximate);
  assert.equal(r.line.length, r.vertexSegment.length);
});
