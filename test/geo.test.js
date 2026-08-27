import assert from 'node:assert/strict';
import { test } from 'node:test';
import { katecToWgs84, haversine, distanceToSegment, sampleLine, lineLength } from '../src/geo.js';

// pyproj(EPSG 정의 기반)으로 뽑은 기준값. 허용 오차 1e-5도 ≈ 1.1m
const FIXTURES = [
  [446881.8, 256007.7, 34.9014461, 128.5108243],
  [400000.0, 600000.0, 38.0027524, 127.9978030],
  [456984.31, 253729.86, 34.8803968, 128.6212079],
  [500000.0, 300000.0, 35.2941054, 129.0972923],
  [350000.0, 700000.0, 38.9022673, 127.4213428],
  [475000.0, 450000.0, 36.6481311, 128.8366244],
];

test('katecToWgs84 는 pyproj 결과와 1m 이내로 일치한다', () => {
  for (const [x, y, lat, lon] of FIXTURES) {
    const [gotLat, gotLon] = katecToWgs84(x, y);
    assert.ok(Math.abs(gotLat - lat) < 1e-5, `lat ${gotLat} != ${lat}`);
    assert.ok(Math.abs(gotLon - lon) < 1e-5, `lon ${gotLon} != ${lon}`);
  }
});

test('haversine 은 알려진 거리를 재현한다', () => {
  // 서울시청 ~ 부산시청 약 325km
  const km = haversine(37.5663, 126.9779, 35.1798, 129.0750);
  assert.ok(km > 320 && km < 330, `${km}`);
  assert.equal(haversine(35, 128, 35, 128), 0);
});

test('distanceToSegment 는 선분 끝을 벗어나면 끝점까지의 거리를 준다', () => {
  const onLine = distanceToSegment(35.0, 128.0, 35.0, 127.9, 35.0, 128.1);
  assert.ok(onLine < 0.001, `${onLine}`);
  const beyond = distanceToSegment(35.0, 128.2, 35.0, 127.9, 35.0, 128.1);
  const direct = haversine(35.0, 128.2, 35.0, 128.1);
  assert.ok(Math.abs(beyond - direct) < 0.05, `${beyond} vs ${direct}`);
});

test('sampleLine 은 첫 점과 끝 점을 항상 포함한다', () => {
  const line = [[35, 128], [35.1, 128], [35.2, 128], [35.3, 128]];
  const s = sampleLine(line, 15);
  assert.deepEqual(s[0], line[0]);
  assert.deepEqual(s[s.length - 1], line[line.length - 1]);
  assert.ok(s.length <= line.length);
});

test('lineLength 는 구간 합과 같다', () => {
  const line = [[35, 128], [35.1, 128], [35.2, 128]];
  const expected = haversine(35, 128, 35.1, 128) + haversine(35.1, 128, 35.2, 128);
  assert.ok(Math.abs(lineLength(line) - expected) < 1e-9);
});

test('utmkToWgs84 는 pyproj(EPSG:5179) 결과와 1m 이내로 일치한다', async () => {
  const { utmkToWgs84 } = await import('../src/geo.js');
  const pairs = [
    [1102463, 1654538, 34.8803968, 128.6212078],
    [1000000, 2000000, 38.0000000, 127.5000000],
    [1150000, 1800000, 36.1855196, 129.1681506],
    [950000, 1900000, 37.0973060, 126.9373358],
  ];
  for (const [x, y, lat, lon] of pairs) {
    const [gotLat, gotLon] = utmkToWgs84(x, y);
    assert.ok(Math.abs(gotLat - lat) < 1e-5, `lat ${gotLat} != ${lat}`);
    assert.ok(Math.abs(gotLon - lon) < 1e-5, `lon ${gotLon} != ${lon}`);
  }
});
