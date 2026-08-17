#!/usr/bin/env python3
"""거제면사무소 → 매미성 경로 위의 교통 CCTV를 찾아 스냅샷으로 저장한다.

ITS 국가교통정보센터 CCTV 오픈API(국토교통부_CCTV 화상자료)에서 경로를 감싸는
사각형(bbox) 안의 CCTV 목록을 받아온 뒤, 경로 폴리라인에서 일정 반경 안에 있는
지점만 남기고 출발지 → 도착지 순서로 정렬한다. ffmpeg 이 있으면 각 지점의 HLS
스트림에서 한 프레임을 따서 이미지로 떨군다.

인증키는 https://www.data.go.kr/data/15040466/openapi.do 또는 https://www.its.go.kr
에서 발급받아 ITS_API_KEY 환경변수 또는 --api-key 로 넘긴다.

사용 예:
    export ITS_API_KEY=발급받은키
    ./geoje_cctv.py list
    ./geoje_cctv.py snap --out snapshots
    ./geoje_cctv.py report --out snapshots --markdown CCTV_REPORT.md

네트워크 없이 로직만 확인하려면 저장해 둔 API 응답을 그대로 먹일 수 있다:
    ./geoje_cctv.py list --from-file cctv_raw.json

주의: 여기서 다루는 것은 공개된 '교통' CCTV 뿐이다. 방범용 CCTV(거제시
CCTV통합관제센터) 영상은 개인정보보호법상 열람 대상이 아니며, 필요한 경우
관할 경찰서나 정보공개청구(https://www.open.go.kr)를 통해야 한다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable, Sequence

API_URL = "http://openapi.its.go.kr/api/NCCTVInfo"
DEFAULT_ROUTE = "route_geoje_myeon_to_maemiseong.json"

# ITS API 는 bbox 한 변이 너무 크면 거절한다. 경로 bbox 에 이만큼(도 단위)만 여유를 준다.
BBOX_PAD_DEG = 0.02

Point = tuple[float, float]  # (lat, lon)


# --------------------------------------------------------------------------
# 기하 계산
# --------------------------------------------------------------------------

def _meters_per_deg(lat: float) -> tuple[float, float]:
    """위도 lat 근처에서 위도 1도 / 경도 1도가 각각 몇 미터인지."""
    return 111_320.0, 111_320.0 * math.cos(math.radians(lat))


def distance_m(a: Point, b: Point) -> float:
    mlat, mlon = _meters_per_deg((a[0] + b[0]) / 2)
    dy = (a[0] - b[0]) * mlat
    dx = (a[1] - b[1]) * mlon
    return math.hypot(dx, dy)


def _point_segment(p: Point, a: Point, b: Point) -> tuple[float, float]:
    """점 p 와 선분 ab 사이 거리(m), 그리고 선분 위 투영 위치 t(0~1)."""
    mlat, mlon = _meters_per_deg(p[0])
    px, py = p[1] * mlon, p[0] * mlat
    ax, ay = a[1] * mlon, a[0] * mlat
    bx, by = b[1] * mlon, b[0] * mlat

    vx, vy = bx - ax, by - ay
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay), 0.0

    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / seg_len_sq))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy), t


def route_offset(p: Point, route: Sequence[Point], cumulative: Sequence[float]) -> tuple[float, float]:
    """경로에서의 최단거리(m)와, 출발지로부터의 진행거리(m)를 함께 돌려준다."""
    best = (float("inf"), 0.0)
    for i in range(len(route) - 1):
        dist, t = _point_segment(p, route[i], route[i + 1])
        if dist < best[0]:
            along = cumulative[i] + t * (cumulative[i + 1] - cumulative[i])
            best = (dist, along)
    return best


def cumulative_lengths(route: Sequence[Point]) -> list[float]:
    out = [0.0]
    for i in range(len(route) - 1):
        out.append(out[-1] + distance_m(route[i], route[i + 1]))
    return out


def bbox_of(route: Sequence[Point], pad: float = BBOX_PAD_DEG) -> tuple[float, float, float, float]:
    """(minX, maxX, minY, maxY) = (min경도, max경도, min위도, max위도)."""
    lats = [p[0] for p in route]
    lons = [p[1] for p in route]
    return min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad


# --------------------------------------------------------------------------
# CCTV 모델 / API
# --------------------------------------------------------------------------

@dataclass
class Cctv:
    name: str
    url: str
    lat: float
    lon: float
    road_type: str
    fmt: str = ""
    resolution: str = ""
    dist_m: float = 0.0
    along_m: float = 0.0
    snapshot: str | None = field(default=None)

    @property
    def slug(self) -> str:
        return re.sub(r"[^\w가-힣]+", "_", self.name).strip("_") or "cctv"


def load_route(path: str) -> tuple[list[Point], dict]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    points = [(float(lat), float(lon)) for lat, lon in raw["points"]]
    if len(points) < 2:
        raise SystemExit(f"{path}: 경로에 점이 2개 이상 필요합니다.")
    return points, raw


def fetch_raw(api_key: str, road_type: str, bbox: tuple[float, float, float, float],
              retries: int = 4, timeout: int = 30) -> dict:
    min_x, max_x, min_y, max_y = bbox
    query = urllib.parse.urlencode({
        "apiKey": api_key,
        "type": road_type,        # its = 국도, ex = 고속도로
        "cctvType": "1",          # 1 = 실시간 스트리밍(HLS)
        "minX": f"{min_x:.6f}",
        "maxX": f"{max_x:.6f}",
        "minY": f"{min_y:.6f}",
        "maxY": f"{max_y:.6f}",
        "getType": "json",
    })
    url = f"{API_URL}?{query}"

    delay = 2
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries:
                raise SystemExit(f"API 호출 실패({road_type}): {exc}")
            print(f"  · 재시도 {attempt}/{retries - 1} ({exc}) — {delay}s 대기", file=sys.stderr)
            time.sleep(delay)
            delay *= 2

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # 인증키 오류 등은 XML 로 돌아온다.
        raise SystemExit(f"API 응답을 JSON 으로 읽지 못했습니다({road_type}):\n{body[:500]}")


def parse_response(payload: dict, road_type: str) -> list[Cctv]:
    data = (payload.get("response") or {}).get("data") or []
    if isinstance(data, dict):  # 결과가 1건이면 dict 로 오는 경우가 있다
        data = [data]

    out: list[Cctv] = []
    for item in data:
        try:
            out.append(Cctv(
                name=str(item.get("cctvname", "")).strip(),
                url=str(item.get("cctvurl", "")).strip(),
                lat=float(item["coordy"]),
                lon=float(item["coordx"]),
                road_type=road_type,
                fmt=str(item.get("cctvformat", "")),
                resolution=str(item.get("cctvresolution", "")),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def collect(args) -> tuple[list[Cctv], list[Point], dict]:
    route, meta = load_route(args.route)
    cumulative = cumulative_lengths(route)
    box = bbox_of(route, args.pad)

    found: list[Cctv] = []
    if args.from_file:
        payload = json.loads(open(args.from_file, encoding="utf-8").read())
        found = parse_response(payload, "file")
    else:
        api_key = args.api_key or os.environ.get("ITS_API_KEY", "")
        if not api_key:
            raise SystemExit("인증키가 없습니다. --api-key 또는 ITS_API_KEY 환경변수를 지정하세요.")
        for road_type in args.road_types:
            print(f"· {road_type} CCTV 조회 중 "
                  f"(bbox {box[0]:.4f},{box[2]:.4f} ~ {box[1]:.4f},{box[3]:.4f})", file=sys.stderr)
            payload = fetch_raw(api_key, road_type, box)
            if args.save_raw:
                path = f"cctv_raw_{road_type}.json"
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                print(f"  원본 응답 저장: {path}", file=sys.stderr)
            found.extend(parse_response(payload, road_type))

    near: list[Cctv] = []
    for cam in found:
        cam.dist_m, cam.along_m = route_offset((cam.lat, cam.lon), route, cumulative)
        if cam.dist_m <= args.radius:
            near.append(cam)

    near.sort(key=lambda c: c.along_m)
    print(f"· 전체 {len(found)}개 중 경로 반경 {args.radius:.0f}m 이내 {len(near)}개",
          file=sys.stderr)
    return near, route, meta


# --------------------------------------------------------------------------
# 스냅샷
# --------------------------------------------------------------------------

def capture(cam: Cctv, out_dir: str, index: int, timeout: int = 40) -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{index:02d}_{cam.slug}.jpg")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-rw_timeout", "15000000",         # 15s (마이크로초)
        "-i", cam.url,
        "-frames:v", "1", "-q:v", "2",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  ✗ {cam.name}: 시간 초과", file=sys.stderr)
        return None

    if proc.returncode != 0 or not os.path.exists(path):
        detail = (proc.stderr or "").strip().splitlines()
        print(f"  ✗ {cam.name}: {detail[-1] if detail else '캡처 실패'}", file=sys.stderr)
        return None

    cam.snapshot = path
    return path


# --------------------------------------------------------------------------
# 출력
# --------------------------------------------------------------------------

def print_table(cams: Iterable[Cctv]) -> None:
    cams = list(cams)
    if not cams:
        print("경로 반경 안에서 찾은 CCTV 가 없습니다. --radius 를 늘려보세요.")
        return
    print(f"{'#':>2}  {'진행(km)':>8}  {'이격(m)':>7}  {'구분':<5}  이름")
    print("-" * 72)
    for i, cam in enumerate(cams, 1):
        print(f"{i:>2}  {cam.along_m / 1000:>8.1f}  {cam.dist_m:>7.0f}  "
              f"{cam.road_type:<5}  {cam.name}")


def write_markdown(cams: Sequence[Cctv], meta: dict, path: str, radius: float) -> None:
    lines = [
        f"# {meta.get('name', '경로')} CCTV",
        "",
        f"경로 폴리라인 반경 **{radius:.0f}m** 이내의 교통 CCTV {len(cams)}개 "
        f"(출발지 기준 진행거리 순).",
        "",
        "| # | 진행(km) | 이격(m) | 구분 | 지점 | 스트림 | 스냅샷 |",
        "|---:|---:|---:|:--|:--|:--|:--|",
    ]
    for i, cam in enumerate(cams, 1):
        shot = f"![{cam.name}]({cam.snapshot})" if cam.snapshot else "—"
        lines.append(
            f"| {i} | {cam.along_m / 1000:.1f} | {cam.dist_m:.0f} | {cam.road_type} | "
            f"{cam.name} | [스트림]({cam.url}) | {shot} |"
        )
    lines += [
        "",
        "> 스트림 URL 은 HLS 라 브라우저에서 바로 안 열릴 수 있습니다. VLC 등에서 "
        "`네트워크 스트림 열기`로 붙이거나 위 스냅샷을 참고하세요.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"· 리포트 작성: {path}", file=sys.stderr)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="거제면사무소 → 매미성 경로 위 교통 CCTV 조회 / 스냅샷",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["list", "snap", "report"],
                        help="list=목록만, snap=스냅샷 저장, report=스냅샷+마크다운")
    parser.add_argument("--route", default=DEFAULT_ROUTE, help=f"경로 JSON (기본 {DEFAULT_ROUTE})")
    parser.add_argument("--api-key", default=None, help="ITS 인증키 (기본 ITS_API_KEY 환경변수)")
    parser.add_argument("--road-types", nargs="+", default=["its"], choices=["its", "ex"],
                        help="its=국도, ex=고속도로 (기본 its)")
    parser.add_argument("--radius", type=float, default=300.0,
                        help="경로에서 이 거리(m) 안의 CCTV 만 (기본 300)")
    parser.add_argument("--pad", type=float, default=BBOX_PAD_DEG,
                        help=f"조회 bbox 여유 (도 단위, 기본 {BBOX_PAD_DEG})")
    parser.add_argument("--out", default="snapshots", help="스냅샷 저장 폴더 (기본 snapshots)")
    parser.add_argument("--markdown", default="CCTV_REPORT.md", help="report 명령의 출력 파일")
    parser.add_argument("--from-file", default=None,
                        help="API 대신 저장해 둔 응답 JSON 사용 (오프라인 확인용)")
    parser.add_argument("--save-raw", action="store_true", help="API 원본 응답도 파일로 저장")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cams, _route, meta = collect(args)

    if args.command in ("snap", "report"):
        if shutil.which("ffmpeg"):
            for i, cam in enumerate(cams, 1):
                print(f"· [{i}/{len(cams)}] {cam.name}", file=sys.stderr)
                capture(cam, args.out, i)
        else:
            print("· ffmpeg 이 없어 스냅샷은 건너뜁니다 "
                  "(apt install ffmpeg / brew install ffmpeg). 스트림 URL 은 그대로 출력됩니다.",
                  file=sys.stderr)

    print_table(cams)

    if args.command == "report":
        write_markdown(cams, meta, args.markdown, args.radius)

    return 0


if __name__ == "__main__":
    sys.exit(main())
