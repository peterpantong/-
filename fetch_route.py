#!/usr/bin/env python3
"""실제 도로를 따라가는 경로 좌표를 받아 geoje_cctv.py 용 route JSON 으로 저장한다.

geoje_cctv.py 는 경로 폴리라인 반경으로 CCTV 를 걸러내므로, 직선으로 이어붙인
근사 경로를 쓰면 실제 도로에서 벗어난 구간의 CCTV 를 놓치거나 엉뚱한 걸 줍는다.
이 스크립트로 실제 도로 형상을 받아 route 파일을 갈아끼우면 그 문제가 사라진다.

제공자(provider):
  kakao  카카오모빌리티 길찾기 API — 국내 도로망 기준. 가장 정확하다.
         https://developers.kakao.com 에서 REST API 키 발급 후
         KAKAO_REST_API_KEY 환경변수 또는 --key 로 전달.
  osrm   OSRM 서버 (기본값은 공개 데모 서버, 키 불필요). OSM 기반.
  gpx    티맵/카카오맵/스트라바 등에서 내보낸 GPX 파일을 읽어 변환.
  json   [[lat,lon], ...] 또는 GeoJSON LineString 이 든 파일을 읽어 변환.

사용 예:
    export KAKAO_REST_API_KEY=발급받은키
    ./fetch_route.py --provider kakao \
        --start 34.8506,128.5817 --end 34.9846,128.7115 \
        --name "거제면사무소 → 매미성" \
        --out route_geoje_myeon_to_maemiseong.json

    ./fetch_route.py --provider osrm --start 34.8506,128.5817 --end 34.9846,128.7115
    ./fetch_route.py --provider gpx --input 매미성.gpx

좌표는 전부 "위도,경도" 순서로 입력한다 (지도 앱에서 복사하는 순서 그대로).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Sequence

Point = tuple[float, float]  # (lat, lon)

KAKAO_URL = "https://apis-navi.kakaomobility.com/v1/directions"
DEFAULT_OSRM = "https://router.project-osrm.org"


# --------------------------------------------------------------------------
# 공통 유틸
# --------------------------------------------------------------------------

def parse_latlon(text: str) -> Point:
    try:
        lat_s, lon_s = text.split(",")
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        raise SystemExit(f"좌표 형식이 잘못됐습니다: {text!r} (예: 34.8506,128.5817)")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise SystemExit(f"좌표 범위를 벗어났습니다: {text!r} — '위도,경도' 순서가 맞나요?")
    return lat, lon


def _meters_per_deg(lat: float) -> tuple[float, float]:
    return 111_320.0, 111_320.0 * math.cos(math.radians(lat))


def distance_m(a: Point, b: Point) -> float:
    mlat, mlon = _meters_per_deg((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * mlat, (a[1] - b[1]) * mlon)


def path_length_m(points: Sequence[Point]) -> float:
    return sum(distance_m(points[i], points[i + 1]) for i in range(len(points) - 1))


def _perpendicular_m(p: Point, a: Point, b: Point) -> float:
    mlat, mlon = _meters_per_deg(p[0])
    px, py = p[1] * mlon, p[0] * mlat
    ax, ay = a[1] * mlon, a[0] * mlat
    bx, by = b[1] * mlon, b[0] * mlat
    vx, vy = bx - ax, by - ay
    seg_sq = vx * vx + vy * vy
    if seg_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / seg_sq))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def simplify(points: Sequence[Point], tolerance_m: float) -> list[Point]:
    """Douglas-Peucker. 도로 형상은 유지하면서 점 개수를 줄인다."""
    if tolerance_m <= 0 or len(points) < 3:
        return list(points)

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        worst, worst_i = 0.0, -1
        for i in range(start + 1, end):
            d = _perpendicular_m(points[i], points[start], points[end])
            if d > worst:
                worst, worst_i = d, i
        if worst > tolerance_m:
            keep[worst_i] = True
            stack.append((start, worst_i))
            stack.append((worst_i, end))
    return [p for p, k in zip(points, keep) if k]


def http_get(url: str, headers: dict | None = None, retries: int = 4, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=headers or {})
    delay = 2
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            raise SystemExit(f"HTTP {exc.code} — {body}")
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries:
                raise SystemExit(f"요청 실패: {exc}")
            print(f"  · 재시도 {attempt}/{retries - 1} ({exc}) — {delay}s 대기", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise SystemExit("unreachable")


# --------------------------------------------------------------------------
# provider: kakao
# --------------------------------------------------------------------------

def from_kakao(start: Point, end: Point, vias: Sequence[Point], key: str) -> tuple[list[Point], dict]:
    params = {
        "origin": f"{start[1]},{start[0]}",       # x=경도, y=위도
        "destination": f"{end[1]},{end[0]}",
        "priority": "RECOMMEND",
        "road_details": "true",
    }
    if vias:
        params["waypoints"] = "|".join(f"{lon},{lat}" for lat, lon in vias)

    body = http_get(f"{KAKAO_URL}?{urllib.parse.urlencode(params)}",
                    headers={"Authorization": f"KakaoAK {key}"})
    payload = json.loads(body)

    routes = payload.get("routes") or []
    if not routes:
        raise SystemExit(f"경로를 찾지 못했습니다: {body[:300]}")
    route = routes[0]
    if route.get("result_code", 0) != 0:
        raise SystemExit(f"카카오 응답 오류 {route.get('result_code')}: {route.get('result_msg')}")

    points: list[Point] = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            verts = road.get("vertexes", [])
            for i in range(0, len(verts) - 1, 2):
                points.append((float(verts[i + 1]), float(verts[i])))  # (lat, lon)

    summary = route.get("summary", {})
    meta = {
        "provider": "kakao-mobility-directions",
        "api_distance_m": summary.get("distance"),
        "api_duration_s": summary.get("duration"),
    }
    return points, meta


# --------------------------------------------------------------------------
# provider: osrm
# --------------------------------------------------------------------------

def decode_polyline(encoded: str, precision: int = 5) -> list[Point]:
    """Google/OSRM encoded polyline → [(lat, lon), ...]"""
    factor = float(10 ** precision)
    coords: list[Point] = []
    index = lat = lon = 0

    while index < len(encoded):
        for axis in range(2):
            shift = result = 0
            while True:
                if index >= len(encoded):
                    raise SystemExit("polyline 문자열이 중간에 끊겼습니다.")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if axis == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return coords


def from_osrm(start: Point, end: Point, vias: Sequence[Point], server: str) -> tuple[list[Point], dict]:
    chain = [start, *vias, end]
    coords = ";".join(f"{lon},{lat}" for lat, lon in chain)
    url = (f"{server.rstrip('/')}/route/v1/driving/{coords}"
           f"?overview=full&geometries=polyline&steps=false")
    payload = json.loads(http_get(url))

    if payload.get("code") != "Ok":
        raise SystemExit(f"OSRM 오류: {payload.get('code')} {payload.get('message', '')}")
    route = payload["routes"][0]
    points = decode_polyline(route["geometry"])
    meta = {
        "provider": f"osrm ({server})",
        "api_distance_m": route.get("distance"),
        "api_duration_s": route.get("duration"),
    }
    return points, meta


# --------------------------------------------------------------------------
# provider: gpx / json
# --------------------------------------------------------------------------

def from_gpx(path: str) -> tuple[list[Point], dict]:
    root = ET.parse(path).getroot()
    ns = {"gpx": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    tags = ["gpx:trk//gpx:trkpt", "gpx:rte//gpx:rtept"] if ns else ["trk//trkpt", "rte//rtept"]

    points: list[Point] = []
    for tag in tags:
        for node in root.findall(f".//{tag}", ns):
            points.append((float(node.attrib["lat"]), float(node.attrib["lon"])))
        if points:
            break
    if not points:
        raise SystemExit(f"{path}: trkpt/rtept 를 찾지 못했습니다.")
    return points, {"provider": f"gpx ({os.path.basename(path)})"}


def from_json(path: str) -> tuple[list[Point], dict]:
    raw = json.load(open(path, encoding="utf-8"))

    if isinstance(raw, dict):
        if raw.get("type") == "Feature":
            raw = raw["geometry"]
        if raw.get("type") == "LineString":  # GeoJSON 은 [경도, 위도] 순서
            pts = [(float(lat), float(lon)) for lon, lat in raw["coordinates"]]
            return pts, {"provider": f"geojson ({os.path.basename(path)})"}
        if "points" in raw:
            pts = [(float(a), float(b)) for a, b in raw["points"]]
            return pts, {"provider": f"route json ({os.path.basename(path)})"}
        raise SystemExit(f"{path}: LineString 또는 points 키가 필요합니다.")

    pts = [(float(a), float(b)) for a, b in raw]
    return pts, {"provider": f"json ({os.path.basename(path)})"}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="실제 도로 경로 좌표를 받아 geoje_cctv.py 용 route JSON 을 만든다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--provider", required=True, choices=["kakao", "osrm", "gpx", "json"])
    p.add_argument("--start", help="출발지 '위도,경도' (kakao/osrm)")
    p.add_argument("--end", help="도착지 '위도,경도' (kakao/osrm)")
    p.add_argument("--via", action="append", default=[],
                   help="경유지 '위도,경도' (여러 번 지정 가능)")
    p.add_argument("--input", help="gpx/json provider 의 입력 파일")
    p.add_argument("--key", default=None, help="카카오 REST API 키 (기본 KAKAO_REST_API_KEY)")
    p.add_argument("--osrm-server", default=DEFAULT_OSRM, help=f"OSRM 서버 (기본 {DEFAULT_OSRM})")
    p.add_argument("--simplify", type=float, default=20.0,
                   help="이 오차(m) 안에서 점 개수를 줄인다. 0 이면 원본 유지 (기본 20)")
    p.add_argument("--name", default="거제면사무소 → 매미성", help="경로 이름")
    p.add_argument("--out", default="route_geoje_myeon_to_maemiseong.json", help="출력 파일")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.provider in ("kakao", "osrm"):
        if not (args.start and args.end):
            raise SystemExit("--start 와 --end 가 필요합니다.")
        start, end = parse_latlon(args.start), parse_latlon(args.end)
        vias = [parse_latlon(v) for v in args.via]
        if args.provider == "kakao":
            key = args.key or os.environ.get("KAKAO_REST_API_KEY", "")
            if not key:
                raise SystemExit("카카오 키가 없습니다. --key 또는 KAKAO_REST_API_KEY 를 지정하세요.")
            points, meta = from_kakao(start, end, vias, key)
        else:
            points, meta = from_osrm(start, end, vias, args.osrm_server)
    else:
        if not args.input:
            raise SystemExit(f"--provider {args.provider} 에는 --input 이 필요합니다.")
        points, meta = from_gpx(args.input) if args.provider == "gpx" else from_json(args.input)

    if len(points) < 2:
        raise SystemExit("경로에 점이 2개 이상 필요합니다.")

    raw_count = len(points)
    points = simplify(points, args.simplify)
    length_km = path_length_m(points) / 1000

    doc = {
        "name": args.name,
        "note": "실제 도로 경로 좌표. fetch_route.py 로 생성됨.",
        "source": meta["provider"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "length_km": round(length_km, 2),
        "point_count": len(points),
        "simplify_tolerance_m": args.simplify,
        "points": "@@POINTS@@",
    }
    for key in ("api_distance_m", "api_duration_s"):
        if meta.get(key) is not None:
            doc[key] = meta[key]

    # 좌표는 한 점당 한 줄로 — 수백 점짜리 폴리라인이 indent 로 터지지 않게.
    rows = ",\n".join(f"    [{lat:.6f}, {lon:.6f}]" for lat, lon in points)
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    text = text.replace('"@@POINTS@@"', f"[\n{rows}\n  ]") + "\n"
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)

    print(f"· {meta['provider']}", file=sys.stderr)
    print(f"· {raw_count}점 → {len(points)}점 (오차 {args.simplify:g}m), 길이 {length_km:.1f}km",
          file=sys.stderr)
    if meta.get("api_distance_m"):
        print(f"· API 보고 거리 {meta['api_distance_m'] / 1000:.1f}km", file=sys.stderr)
    print(f"· 저장: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
