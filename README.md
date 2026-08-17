# 거제면사무소 → 매미성 경로 CCTV 확인

거제시 거제면사무소에서 장목면 복항마을 **매미성**까지 가는 길(국도 14호선 + 지방도 1018호선)
위에 있는 **공개 교통 CCTV**를 찾아 목록·스냅샷·마크다운 리포트로 뽑아내는 스크립트입니다.

- `geoje_cctv.py` — 조회 / 스냅샷 / 리포트 CLI (파이썬 표준 라이브러리만 사용)
- `fetch_route.py` — 실제 도로 경로 좌표를 받아 route 파일을 생성
- `route_geoje_myeon_to_maemiseong.json` — 경로 폴리라인 (**현재는 근사 플레이스홀더**)

## 준비

1. 인증키 발급 — [공공데이터포털 · 국토교통부_CCTV 화상자료](https://www.data.go.kr/data/15040466/openapi.do)
   또는 [ITS 국가교통정보센터](https://www.its.go.kr) 회원가입 후 `마이페이지 → 인증키 발급`
2. 스냅샷을 뽑으려면 `ffmpeg` 설치 (없어도 목록·리포트는 동작하고 스트림 URL 만 남습니다)

```bash
export ITS_API_KEY=발급받은키
```

## 사용법

```bash
# 가장 간단 — 거제시 전역 CCTV 를 경로 진행 순서로 훑기 (경로 정확도 신경 안 써도 됨)
./geoje_cctv.py list --area geoje

# 경로 반경 300m 안의 CCTV 목록 (출발지 → 도착지 순)
./geoje_cctv.py list

# 각 지점 HLS 스트림에서 한 프레임씩 캡처해 snapshots/ 에 저장
./geoje_cctv.py snap --out snapshots

# 스냅샷 + 마크다운 리포트
./geoje_cctv.py report --out snapshots --markdown CCTV_REPORT.md
```

자주 쓰는 옵션:

| 옵션 | 설명 |
|---|---|
| `--area geoje` | 경로 반경 대신 **거제시 전역** bbox 로 조회 (반경 제한 없음) |
| `--sort route\|dist\|name` | 경로 진행순 / 경로에서 가까운순 / 이름순 (기본 route) |
| `--radius 500` | 경로에서 이 거리(m) 안의 CCTV 만 남김 (route 모드 기본 300) |
| `--road-types its ex` | `its` 국도, `ex` 고속도로. 기본은 `its` |
| `--route my_route.json` | 다른 경로 파일 사용 |
| `--save-raw` | API 원본 응답을 `cctv_raw_*.json` 으로 저장 |
| `--from-file cctv_raw_its.json` | API 대신 저장해 둔 응답으로 실행 (오프라인 확인용) |

## 동작 방식

1. 경로 폴리라인을 감싸는 사각형(bbox)에 여유를 붙여 `openapi.its.go.kr/api/NCCTVInfo` 를 호출
   (`cctvType=1` → 실시간 HLS 스트림)
2. 받은 지점들을 경로 폴리라인과의 최단거리로 걸러내고, **출발지로부터의 진행거리** 순으로 정렬
3. `ffmpeg -frames:v 1` 로 스트림에서 한 프레임만 떠서 JPG 저장
4. 표 + 이미지가 들어간 마크다운 리포트 작성

## 두 가지 사용 방식

**대충 훑기 (`--area geoje`)** — 경로 정확도가 필요 없을 때. 거제시 전체 bbox 로 조회해
잡히는 교통 CCTV 를 전부 가져오고, 표시는 경로 진행 순서로 정렬합니다. `이격` 열을 보면
어떤 게 실제 경로 위이고 어떤 게 딴 동네(둔덕·동부·남부면 등)인지 바로 구분됩니다.
거제시 CCTV 자체가 많지 않아 전역으로 받아도 목록이 부담스럽지 않습니다.

**경로 주변만 (`--area route`, 기본값)** — 반경 필터를 걸어 경로 위 지점만 남깁니다.
이 모드는 경로 폴리라인 정확도에 결과가 좌우됩니다.

## 경로 파일을 실제 좌표로 교체하기 (선택)

저장소의 `route_geoje_myeon_to_maemiseong.json` 은 **직선으로 이어붙인 근사 경로**입니다
(진행거리 약 19km, 실제 주행거리는 약 35km). `--area geoje` 로 쓸 거면 이대로 둬도
충분하고, `--area route` 로 촘촘하게 걸러내고 싶을 때만 아래로 갈아끼우면 됩니다.

```bash
# 카카오모빌리티 길찾기 — 국내 도로망 기준, 가장 정확
export KAKAO_REST_API_KEY=발급받은키   # https://developers.kakao.com
./fetch_route.py --provider kakao \
    --start 34.8506,128.5817 --end 34.9846,128.7115

# 키 없이 쓰려면 OSRM (OSM 기반 공개 데모 서버)
./fetch_route.py --provider osrm --start 34.8506,128.5817 --end 34.9846,128.7115

# 티맵/카카오맵에서 내보낸 GPX 나 GeoJSON 이 이미 있다면
./fetch_route.py --provider gpx  --input 매미성.gpx
./fetch_route.py --provider json --input route.geojson
```

좌표는 전부 **`위도,경도`** 순서로 넣습니다. 경유지는 `--via 34.9090,128.6390` 처럼 여러 번
지정할 수 있고, `--simplify 20`(기본값)은 20m 오차 안에서 점 개수를 줄여 파일을 가볍게 합니다.
원본 그대로 두려면 `--simplify 0`.

출력 파일에는 좌표뿐 아니라 `source`, `length_km`, `api_distance_m` 이 함께 기록되므로,
API가 보고한 거리와 폴리라인 실측 길이를 비교해 경로가 제대로 잡혔는지 바로 확인할 수 있습니다.
`points` 는 `[위도, 경도]` 배열이라 직접 손으로 고쳐도 됩니다.

## 거제시 CCTV 대략 어디에 있나

> 아래 구간표는 도로망·행정구역 기준으로 정리한 **예상 커버리지**입니다. 실제 지점 이름과
> 개수는 운영기관이 수시로 바꾸므로, 확정 목록은 반드시 아래 명령으로 뽑아 확인하세요.
> (지점명을 지어내지 않으려고 일부러 비워둔 자리입니다.)

### 운영 주체별 — 어떤 CCTV가 잡히나

| 출처 | 대상 | 이 스크립트로 조회 |
|---|---|:--:|
| 국토교통부 (ITS) | **국도 14호선** 축 — 거제 전 구간의 주요 교차로·터널·교량 | O (`--road-types its`) |
| 한국도로공사 | 고속도로 구간 | O (`--road-types ex`) |
| 거제시 교통정보센터 | 고현·장평·옥포 등 **시내 도심 교차로** | 일부 (ITS 연계분만) |
| GK해상도로 | **거가대교** 본선 | X — [별도 사이트](https://www.gklink.com/page/roadinfo/realtraffic/pop_cctv04.php) |
| 거제시 방범·다목적 CCTV | 마을·공원·해수욕장 등 | X — 영상 비공개 (위치정보만 공개) |

### 경로(거제면 → 매미성)가 지나는 구간

| 구간 | 성격 | CCTV 밀도 (예상) |
|---|---|---|
| 거제면 (서상리 일대) | 지방도·군도, 면 소재지 | 낮음 |
| 거제면 → 사등면 | 지방도 1018 산간 구간 | 매우 낮음 — **공백 구간** |
| 고현·장평 (신현 도심) | 국도 14호선 + 시내 간선, 거제 최대 교통량 | **높음** |
| 연초면 | 국도 14호선 본선 | 중간 |
| 하청면 | 국도 14호선 해안 구간 | 낮음 |
| 장목면 (복항·시방) | 국도 14호선 종점부, 거가대교 접속 | 중간 |

즉 **고현·장평 도심과 장목 접속부는 화면이 잘 나오고, 거제면~사등 산간 구간은 비어 있을**
가능성이 큽니다. 그 구간은 CCTV 대신 로드뷰를 보는 편이 낫습니다.

### 실제 목록 뽑기

```bash
./geoje_cctv.py list --area geoje --sort name        # 이름순 전체 목록
./geoje_cctv.py report --area geoje --markdown CCTV_LIST.md   # 마크다운 표로 저장
```

`CCTV_LIST.md` 가 만들어지면 그 표를 여기 아래에 붙여넣으면 됩니다.

<!-- 여기에 ./geoje_cctv.py report 결과 표를 붙여넣으세요 -->

위치 정보만 필요하고 영상은 필요 없다면(방범 CCTV 포함 전수 목록), 별도 데이터셋이 있습니다:
[거제시 CCTV현황 (거제시 데이터포털)](https://data.geoje.go.kr/index.geoje?menuCd=DOM_000000204001001000&apiIdx=15120165)
— 소재지 지번주소, 설치목적, 카메라 대수, 화소수, 설치년월, 위도·경도가 들어 있습니다.

## 스크립트 없이 바로 볼 수 있는 곳

| 구간 | 사이트 |
|---|---|
| 거제 시내·시도 (고현, 연초, 장평 등) | [거제시 교통정보센터](https://its.geoje.go.kr/trafficinfo/cctvInfo.do) |
| 국도 14호선 등 국도·고속도로 | [ITS 국가교통정보센터 CCTV 지도](https://its.go.kr/map/cctv) |
| 전국 통합 목록 | [UTIC 도시교통정보센터](http://www.utic.go.kr/traffic/cctvList.do?area=) |
| 부산 방면 진입 | [거가대교 GK해상도로](https://www.gklink.com/page/roadinfo/realtraffic/pop_cctv04.php) |
| 생활 CCTV (30초 제한 재생) | [거제시 대시민 CCTV 서비스](https://www.geoje.go.kr/safety/cctv.do) |

## 한계와 주의사항

- 여기서 다루는 것은 **공개된 교통 CCTV** 뿐입니다. 방범용 CCTV(거제시 CCTV통합관제센터)
  영상은 개인정보보호법상 일반 열람 대상이 아니며, 사고·분실 등 사유가 있으면 관할 경찰서
  또는 [정보공개청구](https://www.open.go.kr)를 통해야 합니다. 보관기간이 대개 30일이라
  신청은 빠를수록 좋습니다.
- 교통 CCTV는 **실시간만 제공**되고 과거 녹화분은 공개되지 않습니다. 특정 시각 화면이
  필요하면 이 스크립트를 cron 등으로 주기 실행해 미리 쌓아두거나, 도로관리청
  (국도 14호선 → 부산지방국토관리청 진주국토관리사무소)에 요청해야 합니다.
- 거제면~하청 사이 지방도·농어촌도로 구간은 CCTV 밀도가 낮아 **공백 구간**이 생깁니다.
  그 구간은 카카오맵/네이버 로드뷰 최신 촬영본이 더 실용적입니다.
