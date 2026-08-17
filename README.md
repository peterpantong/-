# 부곡CC 홀별 코스공략 야디지북

> 전인민의 보기플레이를 위하여

부곡컨트리클럽(경남 창녕) 라운드용 **홀별 코스공략 야디지북 PDF** 생성기.
JSON 한 개에 코스 데이터를 적어 넣으면 A4 22페이지짜리 야디지북이 나옵니다.

## 구성

| 페이지 | 내용 |
|---|---|
| 1 | 표지 — 코스 개요, 홀/파 띠, 사용법 |
| 2 | 스코어카드 — 18홀 파·핸디캡·티별 거리, OUT/IN 합계 |
| 3 | 보기플레이 기본 전략 + 내 클럽 거리표 + 티오프 전 체크리스트 |
| 4~21 | 홀 페이지 18장 — 홀 도면, 그린 정보, 해저드, 공략 포인트, 보기 플랜, 메모, 4라운드 스코어 기록 |
| 22 | 라운드 기록 시트 (2라운드분) + 3줄 회고 |

홀 도면은 데이터에서 벡터로 그립니다 — 페어웨이/도그렉, 벙커·해저드·OB 위치,
그린 크기, 그린까지 남은 거리 마커(100/150/200/250m), 보기플레이 기준 티샷 랜딩존.

## 실행

```bash
pip install -r requirements.txt

python build.py                                  # data/bugok_cc.json -> out/부곡CC_야디지북.pdf
python build.py --tee champion                   # 기준 티 변경 (champion/regular/lady)
python build.py --holes 1 --out out/1번홀_샘플.pdf # 일부 홀만 (1 / 1-3 / 1,5,9)
python build.py --data data/sample_filled.json --out out/예시_미리보기.pdf
```

## 실제 코스안내도 넣기

홀에 `"image"` 를 지정하면 골프장이 제공하는 **실제 코스안내도**가 페이지 왼쪽 위에 들어가고,
그 아래에 거리 마커·랜딩존이 표시된 전략 개략도가 함께 붙습니다.

```jsonc
{ "hole": 1, "image": "images/course/w-01.png", ... }
```

18홀 전부 부곡CC 공식 코스안내도가 `images/course/` 에 들어가 있습니다.
파일이 없으면 개략도만 그립니다. 자세한 내용은 [images/README.md](images/README.md) 참고.

## 코스 데이터 출처

`data/bugok_cc.json` 은 부곡CC 공식 홈페이지에서 가져온 **실제 코스 데이터로 채워져 있습니다**.

| 항목 | 출처 |
|---|---|
| 파 · 핸디캡 · 티별 거리 | [코스안내 > 전체코스](https://www.bkcc.co.kr/sub2_1) |
| 공략 포인트 · 그린 · 해저드 | [코스안내 > 코스공략](https://www.bkcc.co.kr/sub2_2) |
| 홀별 코스안내도 18장 | `bkcc.co.kr/images/thema/sub/course/` (w-01~09, e-01~09) |

- 전장: 챔피언 6,294m / 레귤러 5,957m / 레이디 5,311m · PAR 72
- 서코스(OUT, 좌청룡) PAR 36 · 3,203m / 동코스(IN, 우백호) PAR 36 · 3,091m
- `shape`(도그렉 방향)와 `elevation`(오르막·내리막)은 공식 코스공략 설명과 코스안내도를 근거로 표기했습니다.
- `green.depth` / `green.width` 처럼 홈페이지에 공개되지 않은 값은 비워 두었습니다 — 라운드하며 채우면 됩니다.

홀 데이터 형식 (본인 관측을 덧붙일 때 참고):

```jsonc
{
  "nine": "out",              // out(서코스/좌청룡) | in(동코스/우백호)
  "hole": 1,
  "par": 4,
  "handicap": 5,
  "shape": "dogleg_left",     // straight | dogleg_left | dogleg_right
  "elevation": "flat",        // flat | uphill | downhill
  "tees": { "champion": 379, "regular": 350, "lady": 327 },   // 미터
  "green": { "depth": 28, "width": 24, "tier": "2단 그린", "break": "좌 → 우" },
  "hazards": [
    { "type": "bunker", "side": "right", "from": 205, "to": 232, "note": "티샷 랜딩존" },
    { "type": "water",  "side": "front" },
    { "type": "ob",     "side": "right", "from": 0, "to": 300 }
  ],
  "keys": ["코너를 질러가면 OB. 좌측 벙커 앞까지만 끊는다"],   // 공략 포인트(직접 작성)
  "bogey_plan": [],           // 비워 두면 거리에서 자동 계산
  "note": "",
  "image": "images/course/w-01.png" // 실제 코스안내도(선택)
}
```

- `type`: `bunker` | `water` | `ob` | `tree` | `slope`
- `side`: `left` | `right` | `center` | `front` | `back` | `greenside_left` | `greenside_right`
- `from`/`to`: 티에서의 거리(m). 그린 주변 해저드는 생략해도 그린 옆에 배치됩니다.

`player.clubs` 에 본인 평균 캐리 거리를 넣으면 홀별 보기 플랜의 클럽 추천이 함께 바뀝니다.

실제 값을 확인할 곳: 부곡CC 스코어카드, 공식 홈페이지 코스안내(<https://www.bkcc.co.kr/sub1_2>),
또는 클럽하우스 문의(055-521-0707).

## 보기 플랜 자동 계산

`bogey_plan` 이 비어 있으면 홀 길이와 `player.clubs` 에서 샷 배분을 역산합니다.

- **파3** — 핀이 아니라 그린 중앙, 미스는 짧은 쪽·넓은 쪽으로
- **파4** — 남은 거리가 150m 이내면 그린 직접 공략, 넘으면 그린 90m 앞으로 레이업 후 풀웨지
- **파5** — 3온을 목표로 두지 않고 세컨을 그린 100m 앞 평지로

파를 노리는 배분이 아니라 **더블보기를 지우는 배분**입니다.

## 폰트

한글 폰트는 이 순서로 찾습니다: `fonts/` 디렉터리 → `koreanize-matplotlib` 패키지가
번들한 나눔고딕 → 시스템 설치 폰트 → reportlab 내장 CID 폰트.
원하는 폰트가 있으면 `fonts/NanumGothic.ttf`, `fonts/NanumGothicBold.ttf` 로 넣어 두면 됩니다.

## 구조

```
build.py                  CLI
yardagebook/course.py     데이터 로딩·검증, 보기 플랜 계산
yardagebook/diagram.py    홀 도면 벡터 드로잉
yardagebook/book.py       페이지 레이아웃
yardagebook/fonts.py      한글 폰트 탐색·등록
data/bugok_cc.json        ← 실제 코스 데이터 (여기를 채우세요)
data/sample_filled.json   레이아웃 확인용 예시 데이터 (실제 거리 아님)
```
