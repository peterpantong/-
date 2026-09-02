# 홀별 스코어맵 · 공략 가이드

> 전인민의 보기플레이를 위하여

**골프장이 제공하는 실제 코스안내도 + 홀별 공략 가이드**를 한 권짜리 A4 PDF(22페이지)로 묶는 생성기.
JSON 한 개에 코스 데이터를 적고 `images/` 에 코스안내도를 넣으면 끝납니다.
코스에 종속된 문구는 전부 데이터에 있고 코드에는 없어서, 골프장을 추가하려면 JSON만 하나 더 만들면 됩니다.

| 코스 | 데이터 파일 | 상태 |
|---|---|---|
| 부곡컨트리클럽 (경남 창녕) | `data/bugok_cc.json` | 거리·파 미입력 |
| 아난티 남해 (경남 남해) | `data/ananti_namhae.json` | **1번홀 완료** (공식 코스안내 기준), 2~18번홀 미입력 |

## 구성

| 페이지 | 내용 |
|---|---|
| 1 | 표지 — 코스 개요, 홀/파 띠, 사용법 |
| 2 | 스코어카드 — 18홀 파·핸디캡·티별 거리, OUT/IN 합계 |
| 3 | 보기플레이 기본 전략 + 내 클럽 거리표 + 티오프 전 체크리스트 |
| 4 | 싱글플레이 전략 + 라운드별 지표 기록표 (GIR·페어웨이·퍼트·업앤다운) |
| 5~22 | 홀 페이지 18장 — 스코어맵(실제 코스안내도) + 그린 상세도 + F/C/B 거리 + 위험구역 + 공략 포인트 + 샷 플랜 + 4라운드 기록칸 |

라운드 기록은 홀마다 페이지 하단 기록칸(4라운드분)에, 라운드 단위 지표는
싱글플레이 전략 페이지의 지표표에 적습니다.

## 두 가지 홀 페이지 형식

`--style` 로 고릅니다.

| | 왼쪽 | 쓰는 경우 |
|---|---|---|
| **`scoremap`** (기본) | 골프장 **실제 코스안내도** 이미지 | 골프장이 안내도를 제공할 때 — 대부분 이 쪽 |
| `yardage` | 데이터로 그린 **벡터 개략도** | 안내도가 없거나, 라운드 중 직접 그려 넣고 싶을 때 |

`scoremap` 이라도 해당 홀 이미지가 없으면 자동으로 개략도로 대체되므로, 이미지를 구한 홀부터
차례로 채워 나가면 됩니다.

### 벡터 개략도 (yardage 형식)

페어웨이/도그렉, 벙커·해저드·OB 위치, 그린 크기, 그린까지 남은 거리 마커(100/150/200/250m),
보기플레이 기준 티샷 랜딩존. 여기에 실제 야디지북의 두 가지 표기를 씁니다:

- **해저드별 티 캐리 상자** — 벙커·해저드 옆에 티 색 점과 함께 각 티에서의 캐리 거리를 쌓아 표시.
  해저드는 코스 위 고정 지점이므로 '그린까지 남은 거리'가 티와 무관하다는 성질로 환산합니다.
  해저드 거리를 어느 티 기준으로 적었는지는 `course.hazard_ref_tee` 로 지정하고,
  생략하면 `--tee` 값을 기준으로 봅니다.
- **그린 앞·중앙·뒤 거리표(F/C/B)** — 티 거리는 관례상 그린 중앙까지이므로
  `green.depth` 의 절반을 앞뒤로 더해 티별로 계산합니다.

## 실행

```bash
pip install -r requirements.txt

python build.py                                  # data/bugok_cc.json -> out/부곡CC_야디지북.pdf
python build.py --data data/ananti_namhae.json --out out/아난티남해_스코어맵.pdf
python build.py --tee blue                       # 기준 티 변경 (black/blue/white/red)
python build.py --level single                   # 홀 페이지 플랜: bogey(기본) / single / both
python build.py --style yardage                  # 홀 페이지 형식: scoremap(기본) / yardage
python build.py --holes 1 --out out/1번홀_샘플.pdf # 일부 홀만 (1 / 1-3 / 1,5,9)
python build.py --data data/sample_filled.json --out out/예시_미리보기.pdf
```

## 실제 코스안내도 넣기 — 파일명만 맞추면 끝

`course.image_prefix` 를 정해 두면 **JSON 을 홀마다 고칠 필요 없이** 파일명 규칙으로 잡힙니다.

```jsonc
"course": { "image_prefix": "ananti", ... }
```

```
images/ananti_hole01.jpg         홀 안내도       -> 페이지 왼쪽 전체
images/ananti_hole01_green.jpg   그린 상세도     -> 오른쪽 '그린' 항목 위
images/ananti_hole02.jpg
...
```

확장자는 `.jpg` `.jpeg` `.png` 를 찾습니다. 특정 홀만 다른 경로를 쓰려면 그 홀에
`"image"` / `"green_image"` 를 직접 적으면 규칙보다 우선합니다. 파일이 없으면 개략도로 대체됩니다.
자세한 내용은 [images/README.md](images/README.md) 참고.

### URL 패턴으로 한 번에 받기

골프장 사이트는 대개 홀 번호만 바뀌는 규칙적인 이미지 주소를 씁니다.
아난티 남해는 이렇습니다:

```
https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-outcourse-hole4.jpg
```

홀 번호 자리를 `{hole}` 로 바꿔 넘기면 한 번에 받아 `images/` 에 규칙대로 저장합니다.

```bash
# OUT 1~9번홀
python tools/fetch_images.py --prefix ananti --holes 1-9 \
  --template "https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-outcourse-hole{hole}.jpg"

# IN 10~18번홀 — URL 이 자체 1~9 번호를 쓰면 offset 으로 맞춥니다
python tools/fetch_images.py --prefix ananti --holes 10-18 --url-hole-offset -9 \
  --template "https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-incourse-hole{hole}.jpg"
```

- `--dry-run` 으로 주소만 먼저 확인할 수 있습니다
- 그린 상세도는 `--green` (→ `_green` 접미사)
- 확장자는 URL 이 아니라 **내용**으로 판별합니다. 404 를 200 HTML 로 돌려주는
  사이트를 걸러내기 위해서입니다
- 이미 있는 파일은 건너뜁니다 (`--overwrite` 로 강제)

### 파일명이 제각각일 때

사이트에서 저장하면 이름이 `hole1.jpg`, `NH_02_view.png`, `3번홀_그린.jpg` 처럼 제각각입니다.
정리 도구가 홀 번호와 그린 여부를 이름에서 뽑아 규칙대로 복사해 줍니다.

```bash
python tools/import_images.py --src ~/Downloads/ananti --prefix ananti --dry-run   # 미리보기
python tools/import_images.py --src ~/Downloads/ananti --prefix ananti             # 실행
```

홀 번호를 못 찾은 파일은 건너뛰고 목록으로 알려주며, 두 파일이 같은 이름으로 겹치면
덮어쓰지 않고 멈춥니다.

## ⚠️ 거리 데이터는 직접 채워야 합니다

두 데이터 파일 모두 **파 / 핸디캡 / 티별 거리가 비어 있습니다(null)**.
골프장 공식 홈페이지(`bkcc.co.kr`, `ananti.kr`)가 이 작업 환경의 네트워크 정책에서
차단되어 실제 스코어카드를 가져올 수 없었고, 확인되지 않은 거리를 지어내지 않았습니다.

지금 상태로 빌드해도 **라운드 중 직접 적어 넣는 백지 가이드**로 바로 쓸 수 있고,
아래 값을 채우면 모든 표·도면·플랜이 실제 값으로 채워집니다.

채워 넣을 곳 (홀당):

```jsonc
{
  "nine": "out",              // out(좌청룡) | in(우백호)
  "hole": 1,
  "par": 4,
  "handicap": 9,
  "shape": "dogleg_right",    // straight | dogleg_left | dogleg_right
  "elevation": "uphill",      // flat | uphill | downhill
  "tees": { "black": 372, "blue": 355, "white": 336, "red": 298 },   // 미터
  "green": { "depth": 28, "width": 24, "tier": "2단 그린", "break": "좌 → 우" },
  "hazards": [
    { "type": "bunker", "side": "right", "from": 205, "to": 232, "note": "티샷 랜딩존" },
    { "type": "water",  "side": "front" },
    { "type": "ob",     "side": "right", "from": 0, "to": 300 }
  ],
  "keys": ["코너를 질러가면 OB. 좌측 벙커 앞까지만 끊는다"],   // 공략 포인트(직접 작성)
  "bogey_plan": [],           // 비워 두면 거리에서 자동 계산
  "single_plan": [],          // 싱글 목표 배분. 비워 두면 자동 계산
  "note": "",
  "image": "",                // 비워 두면 image_prefix 파일명 규칙으로 찾음
  "green_image": ""
}
```

- `type`: `bunker` | `water` | `ob` | `tree` | `slope`
- `side`: `left` | `right` | `center` | `front` | `back` | `greenside_left` | `greenside_right`
- `from`/`to`: 티에서의 거리(m). 그린 주변 해저드는 생략해도 그린 옆에 배치됩니다.

`player.clubs` 에 본인 평균 캐리 거리를 넣으면 두 플랜의 클럽 추천이 함께 바뀝니다.

실제 값을 확인할 곳: 스코어카드, 골프장 공식 홈페이지 코스안내, 또는 클럽하우스 문의.
부곡CC <https://www.bkcc.co.kr/sub1_2> · 055-521-0707 / 아난티 남해 <https://ananti.kr/ko/namhae/NH0201>

## 다른 골프장 추가하기

`data/` 에 JSON 을 하나 더 만들면 됩니다. 코스 이름·주소·코스별 공략 문구까지 전부 데이터에 있습니다.

```jsonc
{
  "course": { "name": "...", "holes": 18, "par": 72, "nines": [...], "notes": [...] },
  "strategy": {
    "course_notes_title": "해안 코스 · 바람 보정",   // 전략 페이지에 이 코스만의 섹션으로 들어감
    "course_notes": ["...", "..."]                  // 생략하면 그 섹션 없이 번호가 자동으로 당겨짐
  },
  "tees": [...], "player": {...}, "holes": [...]
}
```

## 샷 플랜 자동 계산

`bogey_plan` / `single_plan` 이 비어 있으면 홀 길이와 `player.clubs` 에서 샷 배분을 역산합니다.
`--level` 로 홀 페이지에 실을 플랜을 고릅니다 (`bogey` 기본 / `single` / `both`).
전략 페이지는 `--level` 과 무관하게 두 장 다 들어갑니다.

**보기 플랜** — 파를 노리는 배분이 아니라 *더블보기를 지우는* 배분

- **파3** — 핀이 아니라 그린 중앙, 미스는 짧은 쪽·넓은 쪽으로
- **파4** — 남은 거리가 150m 이내면 그린 직접 공략, 넘으면 그린 90m 앞으로 레이업 후 풀웨지
- **파5** — 3온을 목표로 두지 않고 세컨을 그린 100m 앞 평지로

**싱글 플랜** — *GIR 을 늘리고 숏사이드를 피하는* 배분

- **파3** — 그린 중앙. 핀이 에지 5m 안쪽이면 무시
- **파4** — 그린 중앙 기준에서 안전한 쪽으로 4m. 드라이버가 애매한 거리를 남기면 끊어서 풀웨지 거리로
- **파5** — 2온은 ①티샷 페어웨이 ②남은 거리가 최장 클럽 안쪽 ③그린 앞 트임, 셋 다 맞을 때만

## 폰트

한글 폰트는 이 순서로 찾습니다: `fonts/` 디렉터리 → `koreanize-matplotlib` 패키지가
번들한 나눔고딕 → 시스템 설치 폰트 → reportlab 내장 CID 폰트.
원하는 폰트가 있으면 `fonts/NanumGothic.ttf`, `fonts/NanumGothicBold.ttf` 로 넣어 두면 됩니다.

## 구조

```
build.py                  CLI
yardagebook/course.py     데이터 로딩·검증, 보기/싱글 플랜 계산
yardagebook/diagram.py    홀 도면 벡터 드로잉
yardagebook/book.py       페이지 레이아웃
yardagebook/fonts.py      한글 폰트 탐색·등록
tools/fetch_images.py     URL 패턴으로 코스안내도 일괄 내려받기
tools/import_images.py    내려받은 코스안내도 파일명 정리
data/bugok_cc.json        부곡CC 코스 데이터 (여기를 채우세요)
data/ananti_namhae.json   아난티 남해 코스 데이터 (여기를 채우세요)
data/sample_filled.json   레이아웃 확인용 예시 데이터 (실제 거리 아님)
images/                   골프장 제공 코스안내도 이미지
```
