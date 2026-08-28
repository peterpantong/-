import assert from 'node:assert/strict';
import { test } from 'node:test';
import { encodeRoute, decodeRoute, routeName, reverseStops, MAX_STOPS } from '../public/share.js';

const stop = (name, lat, lon, role = 'via') => ({
  role, label: '경유지', text: name, picked: { name, lat, lon },
});
const sample = () => [
  stop('거제면사무소', 34.85106, 128.5904, 'start'),
  stop('합천읍', 35.566, 128.1579),
  stop('구미 사곡역', 36.1002, 128.3533, 'goal'),
];

test('인코딩한 루트를 그대로 복원한다', () => {
  const back = decodeRoute(encodeRoute(sample()));
  assert.equal(back.length, 3);
  assert.deepEqual(back.map((s) => s.role), ['start', 'via', 'goal']);
  assert.equal(back[0].picked.name, '거제면사무소');
  assert.equal(back[2].picked.lat, 36.1002);
  assert.equal(back[1].label, '경유지');
});

test('좌표가 정해지지 않은 정거장은 빠진다', () => {
  const stops = [...sample(), { role: 'goal', label: '도착지', text: '입력중', picked: null }];
  assert.equal(decodeRoute(encodeRoute(stops)).length, 3);
});

test('정거장이 둘 미만이면 빈 문자열', () => {
  assert.equal(encodeRoute([stop('한 곳', 35, 128, 'start')]), '');
  assert.equal(encodeRoute([]), '');
});

test('망가진 입력은 null 로 거절한다', () => {
  assert.equal(decodeRoute(''), null);
  assert.equal(decodeRoute('{{{'), null);
  assert.equal(decodeRoute('[]'), null);
  assert.equal(decodeRoute('[{"n":"a","y":35,"x":128}]'), null, '한 곳뿐');
  assert.equal(decodeRoute('"문자열"'), null);
});

test('국내 범위를 벗어난 좌표는 거절한다', () => {
  assert.equal(decodeRoute('[{"n":"파리","y":48.85,"x":2.35},{"n":"서울","y":37.5,"x":127}]'), null);
  assert.equal(decodeRoute('[{"n":"a","y":null,"x":128},{"n":"b","y":35,"x":128}]'), null);
});

test('정거장 수 상한을 넘기면 거절한다', () => {
  const many = JSON.stringify(Array.from({ length: MAX_STOPS + 1 },
    (_, i) => ({ n: `p${i}`, y: 35 + i * 0.01, x: 128 })));
  assert.equal(decodeRoute(many), null);
});

test('이름이 없으면 좌표로 대신한다', () => {
  const back = decodeRoute('[{"y":35.1,"x":128.2},{"n":"","y":35.2,"x":128.3}]');
  assert.equal(back[0].picked.name, '35.1, 128.2');
  assert.equal(back[1].picked.name, '35.2, 128.3');
});

test('routeName 은 출발과 도착으로 이름을 만든다', () => {
  assert.equal(routeName(sample()), '거제면사무소 → 구미 사곡역 (경유 1)');
  assert.equal(routeName(sample().filter((_, i) => i !== 1)), '거제면사무소 → 구미 사곡역');
  assert.equal(routeName([]), '');
});

test('reverseStops 는 돌아오는 길을 만든다', () => {
  const back = reverseStops(sample());
  assert.deepEqual(back.map((s) => s.picked.name), ['구미 사곡역', '합천읍', '거제면사무소']);
  assert.deepEqual(back.map((s) => s.role), ['start', 'via', 'goal']);
  assert.deepEqual(back.map((s) => s.label), ['출발지', '경유지', '도착지']);
});
