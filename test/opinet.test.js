import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { _internal } from '../src/opinet.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const html = await fs.readFile(path.join(HERE, 'fixtures/opinet-geoje.html'), 'utf8');

test('실제 오피넷 응답에서 주유소를 읽어낸다', () => {
  const list = _internal.parseStations(html);
  assert.equal(list.length, 8);
  const first = list[0];
  assert.equal(first.name, '상동주유소');
  assert.equal(first.brand, 'S-OIL');
  assert.equal(first.prices.gasoline, 1824);
  assert.equal(first.prices.diesel, 1794);
  assert.equal(first.self, true);
  assert.match(first.address, /거제시/);
  // KATEC 좌표가 거제 일대의 위경도로 변환됐는지
  assert.ok(first.lat > 34.5 && first.lat < 35.2, `${first.lat}`);
  assert.ok(first.lon > 128.3 && first.lon < 129.0, `${first.lon}`);
});

test('미판매 자리표시자(99999)와 빈 값은 null 로 정리된다', () => {
  assert.equal(_internal.toPrice('99999'), null);
  assert.equal(_internal.toPrice(''), null);
  assert.equal(_internal.toPrice('0'), null);
  assert.equal(_internal.toPrice('1824'), 1824);
});

test('모든 항목이 좌표와 가격 구조를 갖춘다', () => {
  for (const s of _internal.parseStations(html)) {
    assert.ok(Number.isFinite(s.lat) && Number.isFinite(s.lon), s.name);
    assert.ok('gasoline' in s.prices && 'diesel' in s.prices, s.name);
    assert.ok(s.id && s.name && s.address, s.name);
  }
});
