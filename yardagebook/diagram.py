"""홀 도면(위에서 내려다본 개략도) 벡터 드로잉.

좌표계는 '미터 공간'을 쓴다. 티가 (0, 0), 그린이 위쪽(+y).
draw_hole() 안에서만 포인트 단위로 환산한다.
"""

from __future__ import annotations

import math
from typing import Sequence

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from . import fonts
from .course import Hole

# 팔레트
C_ROUGH = HexColor("#5C7A4A")
C_ROUGH_EDGE = HexColor("#415A34")
C_FAIRWAY = HexColor("#8FBF6B")
C_GREEN = HexColor("#CDE7A0")
C_GREEN_EDGE = HexColor("#6F9B4A")
C_SAND = HexColor("#EADCA6")
C_SAND_EDGE = HexColor("#C2AE71")
C_WATER = HexColor("#7FB2D9")
C_WATER_EDGE = HexColor("#4B84B0")
C_OB = HexColor("#C0392B")
C_TEE = HexColor("#2F3E32")
C_INK = HexColor("#1E2A22")
C_MARK = HexColor("#FFFFFF")

FAIRWAY_W = 32.0      # 페어웨이 폭(m)
ROUGH_W = 21.0        # 페어웨이 바깥 러프 폭(m)
DOGLEG_OFFSET = 42.0  # 도그렉 가로 이동량(m)


# --------------------------------------------------------------------------
# 기하
# --------------------------------------------------------------------------

def centerline(hole: Hole, length: float) -> list[tuple[float, float]]:
    """티 -> 그린 중심선. 도그렉이면 꺾인 점을 하나 넣는다."""
    if hole.shape == "straight":
        return [(0.0, 0.0), (0.0, length)]
    off = DOGLEG_OFFSET if hole.shape == "dogleg_right" else -DOGLEG_OFFSET
    bend = length * 0.55
    return [(0.0, 0.0), (0.0, bend), (off, length)]


def _seg_normal(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return (dy / n, -dx / n)


def offset_polyline(pts: Sequence[tuple[float, float]], dist: float) -> list[tuple[float, float]]:
    """폴리라인을 dist 만큼 평행이동. 꼭짓점은 인접 법선 평균으로 마이터 처리."""
    if len(pts) < 2:
        return list(pts)
    normals = [_seg_normal(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    out: list[tuple[float, float]] = []
    for i, p in enumerate(pts):
        if i == 0:
            nx, ny = normals[0]
        elif i == len(pts) - 1:
            nx, ny = normals[-1]
        else:
            n0, n1 = normals[i - 1], normals[i]
            nx, ny = n0[0] + n1[0], n0[1] + n1[1]
            mag = math.hypot(nx, ny) or 1.0
            nx, ny = nx / mag, ny / mag
            # 마이터 보정: 꺾인 각도만큼 바깥으로 더 밀어준다
            cos_half = max(0.35, n0[0] * nx + n0[1] * ny)
            nx, ny = nx / cos_half, ny / cos_half
        out.append((p[0] + nx * dist, p[1] + ny * dist))
    return out


def _cumulative(pts: Sequence[tuple[float, float]]) -> list[float]:
    acc = [0.0]
    for i in range(len(pts) - 1):
        acc.append(acc[-1] + math.dist(pts[i], pts[i + 1]))
    return acc


def point_at(pts: Sequence[tuple[float, float]], dist: float) -> tuple[float, float, float]:
    """중심선 위 dist 지점의 (x, y, 진행각도rad)."""
    acc = _cumulative(pts)
    total = acc[-1]
    dist = max(0.0, min(dist, total))
    for i in range(len(pts) - 1):
        if dist <= acc[i + 1] or i == len(pts) - 2:
            seg = acc[i + 1] - acc[i] or 1.0
            t = (dist - acc[i]) / seg
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t
            ang = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
            return x, y, ang
    return pts[-1][0], pts[-1][1], math.pi / 2


def path_length(pts: Sequence[tuple[float, float]]) -> float:
    return _cumulative(pts)[-1]


# --------------------------------------------------------------------------
# 드로잉
# --------------------------------------------------------------------------

def tee_distance_to(hole: Hole, hazard_at: float, ref_tee: str, tee_key: str) -> float | None:
    """기준 티에서 hazard_at(m) 인 지점까지의, tee_key 기준 거리.

    해저드는 코스 위의 고정된 지점이므로 '그린까지 남은 거리'는 티가 달라져도
    같다. 그 성질을 이용해 각 티에서의 캐리 거리를 환산한다.
    """
    ref_len = hole.tees.get(ref_tee)
    tee_len = hole.tees.get(tee_key)
    if ref_len is None or tee_len is None:
        return None
    to_green = float(ref_len) - hazard_at
    return float(tee_len) - to_green


def draw_hole(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    hole: Hole,
    tee_key: str,
    show_scale_note: bool = True,
    tees: list[dict] | None = None,
    ref_tee: str = "white",
) -> None:
    """(x, y)를 좌하단으로 하는 w x h 영역에 홀 도면을 그린다.

    tees 를 넘기면 실제 야디지북처럼 해저드마다 '티별 캐리 거리' 상자를 얹는다.
    """
    length = hole.length(tee_key)
    pts = centerline(hole, length)

    # 실제 중심선이 차지하는 폭만큼만 잡아야 직선 홀에서 도면이 얇아지지 않는다.
    xs = [p[0] for p in pts]
    span_m = (max(xs) - min(xs)) + FAIRWAY_W + 2 * ROUGH_W + 8
    depth_m = length * 1.10

    # 가로로 납작한 영역이면 홀을 눕혀 그린다 (티 왼쪽 -> 그린 오른쪽).
    horiz = w / h > 1.15
    if horiz:
        # 홀이 페이지 오른쪽을 향하므로, 플레이어 기준 오른쪽(+x)은 페이지 아래(-y)가 된다.
        scale = min(w / depth_m, h / span_m)
        cx = x + max(w * 0.04, (w - depth_m * scale) / 2)
        cy = y + h / 2 + ((min(xs) + max(xs)) / 2) * scale

        def P(mx: float, my: float) -> tuple[float, float]:
            return (cx + my * scale, cy - mx * scale)
    else:
        scale = min(w / span_m, h / depth_m)
        cx = x + w / 2 - ((min(xs) + max(xs)) / 2) * scale
        # 짧은 홀에서 도면이 아래로 쏠리지 않도록 세로 가운데 정렬
        cy = y + max(h * 0.04, (h - depth_m * scale) / 2)

        def P(mx: float, my: float) -> tuple[float, float]:
            return (cx + mx * scale, cy + my * scale)

    c.saveState()
    c.setLineJoin(1)
    c.setLineCap(1)

    # 배경(러프)
    c.setFillColor(C_ROUGH)
    c.setStrokeColor(C_ROUGH_EDGE)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)

    _clip_rect(c, x, y, w, h)

    # 페어웨이 (파3은 페어웨이 대신 캐리 라인)
    if hole.par == 3:
        _draw_carry_line(c, pts, P)
    else:
        fw_start = min(55.0, length * 0.2)
        fw_end = max(length - 18.0, length * 0.55)
        fpts = _slice_polyline(pts, fw_start, fw_end)
        _fill_corridor(c, fpts, FAIRWAY_W / 2, P, C_FAIRWAY, None)

    # 거리가 입력되지 않은 홀은 추정 거리를 표시하지 않는다(직접 적어 넣는 백지 도면).
    has_data = hole.known and hole.par is not None
    landing = _landing_distance(hole, length) if has_data else None

    if has_data:
        # 거리 마커 (그린 기준 100/150/200m) — 랜딩존과 겹치는 것은 건너뛴다
        _draw_distance_marks(c, pts, length, P, scale, horiz, avoid=landing)

    # 해저드 — 좌표(start/end)가 없는 것들은 겹쳐 보이지 않도록 순서대로 흩어 놓는다.
    no_coord = [hz for hz in hole.hazards if hz.start is None]
    stagger = {id(hz): i for i, hz in enumerate(no_coord)}
    for hz in hole.hazards:
        _draw_hazard(c, hz, pts, length, P, scale, horiz,
                     stagger_idx=stagger.get(id(hz)), stagger_n=len(no_coord))

    # 실제 야디지북처럼 해저드마다 티별 캐리 거리 상자를 얹는다
    if tees and has_data:
        for hz in hole.hazards:
            _draw_carry_box(c, hz, hole, pts, length, P, scale, horiz, tees, ref_tee,
                            bounds=(x, y, w, h))

    # 그린
    _draw_green(c, hole, pts, P, scale, horiz)

    # 티박스
    _draw_tee(c, pts, P, scale, horiz)

    # 랜딩존
    if landing is not None:
        _draw_landing(c, pts, length, landing, P, scale)

    c.restoreState()

    if show_scale_note:
        c.setFont(fonts.regular(), 5.6)
        c.setFillColor(HexColor("#7C8A7E"))
        label = f"개략도 · 흰 숫자는 그린까지 남은 거리 · 전장 {length:.0f}m"
        if not hole.known:
            label = f"개략도 · 거리 미입력(파 기준 {length:.0f}m 가정)"
        c.drawString(x + 1, y - 7.5, label)


def _clip_rect(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    p = c.beginPath()
    p.roundRect(x, y, w, h, 5)
    c.clipPath(p, stroke=0, fill=0)


def _slice_polyline(
    pts: Sequence[tuple[float, float]], start: float, end: float
) -> list[tuple[float, float]]:
    """중심선의 start~end 구간만 잘라낸다(꼭짓점 보존)."""
    acc = _cumulative(pts)
    out = [point_at(pts, start)[:2]]
    for i, d in enumerate(acc):
        if start < d < end:
            out.append(pts[i])
    out.append(point_at(pts, end)[:2])
    return out


def _fill_corridor(c, pts, half_w, P, fill, stroke) -> None:
    left = offset_polyline(pts, half_w)
    right = offset_polyline(pts, -half_w)
    path = c.beginPath()
    first = P(*left[0])
    path.moveTo(*first)
    for p in left[1:]:
        path.lineTo(*P(*p))
    for p in reversed(right):
        path.lineTo(*P(*p))
    path.close()
    c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(0.7)
    c.drawPath(path, stroke=1 if stroke is not None else 0, fill=1)


def _draw_carry_line(c, pts, P) -> None:
    """파3: 티에서 그린까지의 캐리 라인."""
    c.setStrokeColor(HexColor("#FFFFFF99"))
    c.setLineWidth(0.9)
    c.setDash(3, 3)
    path = c.beginPath()
    path.moveTo(*P(*pts[0]))
    for p in pts[1:]:
        path.lineTo(*P(*p))
    c.drawPath(path, stroke=1, fill=0)
    c.setDash()


def _draw_distance_marks(c, pts, length, P, scale, horiz, avoid: float | None = None) -> None:
    c.setFont(fonts.bold(), 5.4)
    for to_green in (100, 150, 200, 250):
        d = length - to_green
        if d < 35 or d > length - 12:
            continue
        if avoid is not None and abs(d - avoid) < 22:
            continue  # 랜딩존 표시와 겹친다
        mx, my, ang = point_at(pts, d)
        nx, ny = math.sin(ang), -math.cos(ang)
        half = FAIRWAY_W / 2 + 3
        a = P(mx + nx * half, my + ny * half)
        b = P(mx - nx * half, my - ny * half)
        c.setStrokeColor(HexColor("#FFFFFF"))
        c.setLineWidth(0.5)
        c.setDash(1.6, 1.6)
        c.line(a[0], a[1], b[0], b[1])
        c.setDash()

        bx, by = P(mx, my)
        c.setFillColor(HexColor("#FFFFFFCC"))
        c.setStrokeColor(HexColor("#4B6B3C"))
        c.setLineWidth(0.4)
        c.roundRect(bx - 8, by - 3.6, 16, 7.2, 2, stroke=1, fill=1)
        c.setFillColor(C_INK)
        c.drawCentredString(bx, by - 1.9, str(to_green))


def _draw_hazard(c, hz, pts, length, P, scale, horiz, stagger_idx=None, stagger_n=1) -> None:
    # 미터 공간의 +x 는 페이지 오른쪽. offset_polyline(+d) 도 오른쪽으로 밀린다.
    side_sign = {"left": -1.0, "right": 1.0, "center": 0.0}.get(hz.side, 0.0)
    if hz.side.startswith("greenside"):
        side_sign = -1.0 if hz.side.endswith("left") else 1.0

    # 좌표(start/end)가 없는 해저드는 전부 같은 자리에 겹치므로, 몇 번째인지에 따라
    # 홀 진행 방향으로 흩어 배치한다 — 실제 위치는 아니지만 라벨이 겹쳐 읽지 못하는 것보다는 낫다.
    if stagger_idx is not None and stagger_n > 1:
        frac = 0.32 + 0.5 * (stagger_idx / (stagger_n - 1))
    else:
        frac = 0.55

    start = hz.start if hz.start is not None else length * frac
    end = hz.end if hz.end is not None else start + 25
    if hz.side == "front":
        start, end = length - 30, length - 15
    elif hz.side == "back":
        start, end = length + 15, length + 30

    if hz.type == "ob":
        seg = _slice_polyline(pts, max(0, min(start, length)), min(length + 10, max(end, start + 30)))
        off = (FAIRWAY_W / 2 + ROUGH_W - 2) * (side_sign or 1.0)
        line = offset_polyline(seg, off)
        c.setStrokeColor(C_OB)
        c.setLineWidth(1.1)
        c.setDash(3, 2)
        path = c.beginPath()
        path.moveTo(*P(*line[0]))
        for p in line[1:]:
            path.lineTo(*P(*p))
        c.drawPath(path, stroke=1, fill=0)
        c.setDash()
        # 라벨은 랜딩존 표시(중간쯤)와 겹치지 않게 티 쪽 1/4 지점에 둔다
        lx, ly, _ = point_at(line, path_length(line) * 0.25)
        mp = P(lx, ly)
        # 라벨 배경을 깔아 러프 위에서도 읽히게 한다
        c.setFillColor(HexColor("#FFFFFFDD"))
        c.setStrokeColor(C_OB)
        c.setLineWidth(0.4)
        c.roundRect(mp[0] - 7, mp[1] - 3.8, 14, 7.6, 2, stroke=1, fill=1)
        c.setFillColor(C_OB)
        c.setFont(fonts.bold(), 5.8)
        c.drawCentredString(mp[0], mp[1] - 2, "OB")
        return

    mid = (start + end) / 2
    mx, my, ang = point_at(pts, max(0.0, min(mid, length + 20)))
    nx, ny = math.sin(ang), -math.cos(ang)
    lateral = (FAIRWAY_W / 2 + 7) * side_sign
    px, py = mx + nx * lateral, my + ny * lateral
    cxp, cyp = P(px, py)

    long_m = max(14.0, abs(end - start))
    along = (long_m / 2) * scale      # 홀 진행 방향 반경
    across = 7.5 * scale              # 좌우 방향 반경
    ex, ey = (along, across) if horiz else (across, along)

    if hz.type == "water":
        c.setFillColor(C_WATER)
        c.setStrokeColor(C_WATER_EDGE)
    elif hz.type == "tree":
        c.setFillColor(HexColor("#3F6B33"))
        c.setStrokeColor(HexColor("#2C4C24"))
    else:  # bunker / slope
        c.setFillColor(C_SAND)
        c.setStrokeColor(C_SAND_EDGE)
    c.setLineWidth(0.5)
    c.ellipse(cxp - ex, cyp - ey, cxp + ex, cyp + ey, stroke=1, fill=1)

    # 실제 코스안내도에 인쇄된 잔여거리 숫자는 축소되면 읽기 어려우므로,
    # 정확한 좌표(start/end)가 없어 캐리박스를 못 그리는 해저드는 원문 표기를
    # 별도 라벨로 다시 그려 가독성을 보완한다.
    if hz.start is None and hz.note:
        _draw_hazard_label(c, hz.note, cxp, cyp - ey)


def _draw_hazard_label(c, text: str, x: float, y: float) -> None:
    label = text if len(text) <= 30 else text[:29] + "…"
    size = 5.3
    c.setFont(fonts.regular(), size)
    w = c.stringWidth(label, fonts.regular(), size)
    pad = 1.6
    box_y = y - 8.5
    c.setFillColor(HexColor("#FFFFFFD0"))
    c.setStrokeColor(HexColor("#00000022"))
    c.setLineWidth(0.3)
    c.roundRect(x - w / 2 - pad, box_y - 3.4, w + pad * 2, 6.4, 1.4, stroke=1, fill=1)
    c.setFillColor(C_INK)
    c.drawCentredString(x, box_y - 1.6, label)


def _draw_carry_box(c, hz, hole, pts, length, P, scale, horiz, tees, ref_tee, bounds) -> None:
    """해저드 옆에 티별 캐리 거리를 쌓아 표시한다 (실제 야디지북 방식).

    OB 처럼 구간 전체에 걸친 것과, 티에서의 거리를 모르는 해저드는 건너뛴다.
    """
    if hz.type == "ob" or hz.start is None:
        return

    # 해저드 앞 끝까지의 캐리를 기준으로 한다 (넘겨야 하는 거리)
    rows: list[tuple[str, float]] = []
    for tee in tees:
        d = tee_distance_to(hole, float(hz.start), ref_tee, tee["key"])
        if d is None or d < 20 or d > length + 30:
            continue
        rows.append((str(tee.get("color", "#000000")), d))
    if not rows:
        return

    # 해저드 위치와 바깥 방향
    side_sign = {"left": -1.0, "right": 1.0, "center": 0.0}.get(hz.side, 0.0)
    if hz.side.startswith("greenside"):
        side_sign = -1.0 if hz.side.endswith("left") else 1.0
    if side_sign == 0.0:
        side_sign = 1.0

    mid = (float(hz.start) + float(hz.end)) / 2 if hz.end is not None else float(hz.start)
    mx, my, ang = point_at(pts, max(0.0, min(mid, length)))
    nx, ny = math.sin(ang), -math.cos(ang)
    lateral = (FAIRWAY_W / 2 + 20) * side_sign
    ax, ay = P(mx + nx * lateral, my + ny * lateral)

    row_h = 6.0
    box_w = 20.0
    box_h = row_h * len(rows) + 3
    bx = ax - box_w / 2
    by = ay - box_h / 2

    # 도면 밖으로 나가지 않게 가둔다
    x0, y0, w0, h0 = bounds
    bx = max(x0 + 1.5, min(bx, x0 + w0 - box_w - 1.5))
    by = max(y0 + 1.5, min(by, y0 + h0 - box_h - 1.5))

    # 어느 해저드의 숫자인지 보이도록 지시선을 먼저 긋는다
    hzx, hzy = P(mx + nx * (FAIRWAY_W / 2 + 7) * side_sign,
                 my + ny * (FAIRWAY_W / 2 + 7) * side_sign)
    c.setStrokeColor(HexColor("#FFFFFFAA"))
    c.setLineWidth(0.5)
    c.line(hzx, hzy, bx + box_w / 2, by + box_h / 2)

    c.setFillColor(HexColor("#FFFFFFE6"))
    c.setStrokeColor(HexColor("#5A6B58"))
    c.setLineWidth(0.4)
    c.roundRect(bx, by, box_w, box_h, 1.5, stroke=1, fill=1)

    for i, (color, dist) in enumerate(rows):
        ry = by + box_h - 3 - (i + 1) * row_h + 1.6
        c.setFillColor(HexColor(color))
        c.setStrokeColor(HexColor("#5A6B58"))
        c.setLineWidth(0.3)
        c.circle(bx + 4, ry + 1.6, 1.7, stroke=1, fill=1)
        c.setFillColor(C_INK)
        c.setFont(fonts.bold(), 5.2)
        c.drawRightString(bx + box_w - 2.5, ry, f"{dist:.0f}")


def _draw_green(c, hole, pts, P, scale, horiz) -> None:
    gx, gy, ang = pts[-1][0], pts[-1][1], math.pi / 2
    depth = float(hole.green.get("depth", 26) or 26)
    width = float(hole.green.get("width", 24) or 24)
    cxp, cyp = P(gx, gy)
    across, along = (width / 2) * scale, (depth / 2) * scale
    rx, ry = (along, across) if horiz else (across, along)

    c.setFillColor(C_GREEN)
    c.setStrokeColor(C_GREEN_EDGE)
    c.setLineWidth(0.8)
    c.ellipse(cxp - rx, cyp - ry, cxp + rx, cyp + ry, stroke=1, fill=1)

    # 핀
    c.setStrokeColor(C_INK)
    c.setLineWidth(0.7)
    c.line(cxp, cyp, cxp, cyp + 9)
    c.setFillColor(C_OB)
    p = c.beginPath()
    p.moveTo(cxp, cyp + 9)
    p.lineTo(cxp + 6, cyp + 6.6)
    p.lineTo(cxp, cyp + 4.4)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _draw_tee(c, pts, P, scale, horiz) -> None:
    tx, ty = P(0, 0)
    across, along = 13 * scale, 7 * scale
    w, h = (along, across) if horiz else (across, along)
    c.setFillColor(C_TEE)
    c.setStrokeColor(HexColor("#FFFFFF"))
    c.setLineWidth(0.5)
    c.rect(tx - w / 2, ty - h / 2, w, h, stroke=1, fill=1)


def _landing_distance(hole: Hole, length: float) -> float | None:
    """보기플레이 기준 티샷 랜딩존까지의 거리(m). 파3은 없음."""
    if hole.par == 3:
        return None
    return min(200.0, length * (0.55 if hole.par == 4 else 0.42))


def _draw_landing(c, pts, length, target, P, scale) -> None:
    mx, my, _ = point_at(pts, target)
    cxp, cyp = P(mx, my)
    r = 15 * scale

    c.setStrokeColor(HexColor("#FFFFFF"))
    c.setLineWidth(0.9)
    c.setDash(2.5, 2)
    c.circle(cxp, cyp, r, stroke=1, fill=0)
    c.setDash()

    # 라벨은 원 오른쪽에 붙여 거리 마커·페어웨이와 겹치지 않게 한다
    lx = cxp + r + 3
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont(fonts.bold(), 5.6)
    c.drawString(lx, cyp + 1.2, f"티샷 {target:.0f}m")
    c.setFont(fonts.regular(), 5.2)
    c.drawString(lx, cyp - 5.2, f"남은 {length - target:.0f}m")
