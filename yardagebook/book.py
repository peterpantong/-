"""야디지북 PDF 페이지 레이아웃."""

from __future__ import annotations

import datetime as _dt
import os

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from . import diagram, fonts
from .course import Course, Hole, bogey_plan, general_keys, single_plan

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

C_INK = HexColor("#1E2A22")
C_MUTED = HexColor("#6B7A6E")
C_LINE = HexColor("#D3DBD2")
C_ACCENT = HexColor("#2F5D3A")
C_ACCENT_LT = HexColor("#EAF1E7")
C_RED = HexColor("#C0392B")
C_BLANK = HexColor("#AEB9AE")


# --------------------------------------------------------------------------
# 텍스트 유틸
# --------------------------------------------------------------------------

def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    """한글은 글자 단위, 영문/숫자는 단어 단위로 줄바꿈."""
    lines: list[str] = []
    line = ""
    token = ""

    def flush_token() -> None:
        nonlocal line, token
        if not token:
            return
        if pdfmetrics.stringWidth(line + token, font, size) > max_w and line:
            lines.append(line.rstrip())
            line = ""
        line += token
        token = ""

    for ch in text:
        if ch == "\n":
            flush_token()
            lines.append(line.rstrip())
            line = ""
            continue
        if ch.isascii() and (ch.isalnum() or ch in ".-/%"):
            token += ch
            continue
        flush_token()
        if pdfmetrics.stringWidth(line + ch, font, size) > max_w and line:
            lines.append(line.rstrip())
            line = ""
        line += ch
    flush_token()
    if line:
        lines.append(line.rstrip())
    return lines or [""]


def para(
    c: Canvas,
    text: str,
    x: float,
    y: float,
    max_w: float,
    size: float = 8,
    leading: float = 11,
    font: str | None = None,
    color=C_INK,
) -> float:
    """왼쪽 정렬 문단을 그리고, 다음 줄의 y를 돌려준다."""
    font = font or fonts.regular()
    c.setFont(font, size)
    c.setFillColor(color)
    for line in wrap(text, font, size, max_w):
        c.drawString(x, y, line)
        y -= leading
    return y


def bullet(c: Canvas, text: str, x: float, y: float, max_w: float, size=8, leading=10.5,
           marker="·", color=C_INK) -> float:
    c.setFont(fonts.bold(), size)
    c.setFillColor(C_ACCENT)
    c.drawString(x, y, marker)
    return para(c, text, x + 8, y, max_w - 8, size=size, leading=leading, color=color)


def blank_line(c: Canvas, x: float, y: float, w: float) -> None:
    """직접 적어 넣는 점선 빈칸."""
    c.setStrokeColor(C_BLANK)
    c.setLineWidth(0.5)
    c.setDash(1, 1.6)
    c.line(x, y, x + w, y)
    c.setDash()


def fmt(v: float | None, suffix: str = "") -> str | None:
    return None if v is None else f"{v:.0f}{suffix}"


LEVELS = ("bogey", "single", "both")


def _plan_kinds(level: str) -> tuple[str, ...]:
    """홀 페이지에 실을 플랜 종류."""
    if level == "single":
        return ("single",)
    if level == "both":
        return ("bogey", "single")
    return ("bogey",)


def _declared_par(course: Course) -> int:
    """코스 전체 파. --holes 로 일부만 뽑아도 설명 문구는 전체 기준이어야 한다."""
    v = course.meta.get("par")
    return int(v) if v else (course.par_total() or 72)


def _declared_holes(course: Course) -> int:
    v = course.meta.get("holes")
    return int(v) if v else (len(course.holes) or 18)


def _data_ref(course: Course) -> str:
    """안내 문구에 쓸 데이터 파일 경로 (저장소 기준 상대경로)."""
    if not course.source_path:
        return "코스 데이터 JSON"
    try:
        return os.path.relpath(os.path.abspath(course.source_path), _REPO_ROOT)
    except ValueError:
        return os.path.basename(course.source_path)


# --------------------------------------------------------------------------
# 페이지
# --------------------------------------------------------------------------

def cover(c: Canvas, course: Course) -> None:
    meta = course.meta
    band_bottom = PAGE_H * 0.58
    c.setFillColor(C_ACCENT)
    c.rect(0, band_bottom, PAGE_W, PAGE_H - band_bottom, stroke=0, fill=1)

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont(fonts.regular(), 10)
    c.drawString(MARGIN, PAGE_H - 26 * mm, meta.get("name_en", ""))

    c.setFont(fonts.bold(), 34)
    c.drawString(MARGIN, PAGE_H - 45 * mm, meta.get("name", ""))

    c.setFont(fonts.regular(), 15)
    c.drawString(MARGIN, PAGE_H - 57 * mm, meta.get("subtitle", ""))

    slogan = meta.get("slogan")
    if slogan:
        c.setStrokeColor(HexColor("#FFFFFF66"))
        c.setLineWidth(0.8)
        c.line(MARGIN, PAGE_H - 70 * mm, PAGE_W - MARGIN, PAGE_H - 70 * mm)
        c.setFont(fonts.bold(), 13)
        c.setFillColor(HexColor("#E8F3E3"))
        c.drawString(MARGIN, PAGE_H - 80 * mm, slogan)

    _cover_hole_strip(c, course, MARGIN, band_bottom + 18 * mm, PAGE_W - 2 * MARGIN)

    # 요약 카드
    y = band_bottom - 22 * mm
    stats = [
        ("홀", f"{meta.get('holes', 18)}"),
        ("파", f"{meta.get('par', 72)}"),
        ("코스", " · ".join(n.get("name", "") for n in meta.get("nines", []))),
    ]
    x = MARGIN
    for label, value in stats:
        c.setFillColor(C_MUTED)
        c.setFont(fonts.regular(), 8)
        c.drawString(x, y + 19, label)
        c.setFillColor(C_INK)
        c.setFont(fonts.bold(), 16)
        c.drawString(x, y, value)
        x += 55 * mm

    y -= 18 * mm
    tel = str(meta.get("tel", "") or "").strip()
    for line in (meta.get("address", ""), f"TEL {tel}" if tel else "", meta.get("web", "")):
        if line.strip():
            c.setFont(fonts.regular(), 9)
            c.setFillColor(C_MUTED)
            c.drawString(MARGIN, y, line)
            y -= 12

    y -= 8
    for note in meta.get("notes", []):
        y = bullet(c, note, MARGIN, y, PAGE_W - 2 * MARGIN, size=8.5, leading=11, color=C_INK) - 3

    if not course.complete:
        y -= 6
        box_h = 26 * mm
        c.setFillColor(HexColor("#FDF3E3"))
        c.setStrokeColor(HexColor("#E0B980"))
        c.setLineWidth(0.8)
        c.roundRect(MARGIN, y - box_h, PAGE_W - 2 * MARGIN, box_h, 4, stroke=1, fill=1)
        ty = y - 9 * mm
        c.setFont(fonts.bold(), 9.5)
        c.setFillColor(HexColor("#8A5A16"))
        c.drawString(MARGIN + 8, ty, "거리 · 파 데이터 미입력")
        para(
            c,
            f"스코어카드의 홀별 파/핸디캡/티별 거리를 {_data_ref(course)} 에 채운 뒤 다시 빌드하면 "
            "모든 표와 도면이 실제 값으로 채워집니다. 빈칸은 라운드 중 직접 적어 넣을 수 있게 점선으로 출력했습니다.",
            MARGIN + 8, ty - 12, PAGE_W - 2 * MARGIN - 16, size=8, leading=10.5, color=HexColor("#8A5A16"),
        )

    # 사용법 — 페이지 하단 고정
    uy = 62 * mm
    c.setFont(fonts.bold(), 10)
    c.setFillColor(C_ACCENT)
    c.drawString(MARGIN, uy, "이 야디지북 쓰는 법")
    uy -= 15
    for item in (
        "라운드 전날: 전략 페이지 두 장(보기플레이 / 싱글플레이)을 읽고, 드라이버를 뺄 홀 3개를 정한다.",
        "홀 도면: 흰 점선 원은 티샷 목표 지점, 흰 숫자는 그린까지 남은 거리(m).",
        "라운드 중: 판단은 티잉그라운드에서 끝내고, 그 다음부터는 홀 페이지의 플랜대로만 친다.",
        "라운드 후: 마지막 기록 페이지에 스코어·퍼트·벌타를 적고 3줄 회고를 남긴다.",
    ):
        uy = bullet(c, item, MARGIN, uy, PAGE_W - 2 * MARGIN, size=8.3, leading=11) - 3

    c.setFont(fonts.regular(), 7.5)
    c.setFillColor(C_MUTED)
    c.drawRightString(PAGE_W - MARGIN, 12 * mm, _dt.date.today().isoformat())
    c.showPage()


def _cover_hole_strip(c: Canvas, course: Course, x: float, y: float, w: float) -> None:
    """표지 하단 띠: 홀 번호와 파를 한눈에."""
    n = len(course.holes)
    if not n:
        return
    cell = w / n
    h = 13 * mm
    c.setFont(fonts.bold(), 7.5)
    for i, hole in enumerate(course.holes):
        cx = x + i * cell
        c.setFillColor(HexColor("#3E7049") if hole.hole <= 9 else HexColor("#356240"))
        c.rect(cx, y, cell - 1.5, h, stroke=0, fill=1)
        c.setFillColor(HexColor("#CFE3CB"))
        c.setFont(fonts.regular(), 6.5)
        c.drawCentredString(cx + (cell - 1.5) / 2, y + h - 5.5 * mm, str(hole.hole))
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont(fonts.bold(), 9)
        c.drawCentredString(cx + (cell - 1.5) / 2, y + 3.2 * mm, str(hole.par) if hole.par else "·")
    c.setFont(fonts.regular(), 6.5)
    c.setFillColor(HexColor("#9FC0A0"))
    c.drawString(x, y - 8, "홀 / 파")


def scorecard(c: Canvas, course: Course) -> None:
    _page_header(c, "스코어카드 · 전체 야디지", "")
    tee_keys = [t["key"] for t in course.tees]

    x0 = MARGIN
    table_w = PAGE_W - 2 * MARGIN
    cols = ["홀", "파", "HDCP"] + [t["label"] for t in course.tees] + ["스코어"]
    widths = [12 * mm, 12 * mm, 16 * mm] + [22 * mm] * len(tee_keys) + [0]
    widths[-1] = table_w - sum(widths[:-1])

    y = PAGE_H - 32 * mm

    def row(cells, bold_row=False, fill=None, height=7.6 * mm):
        nonlocal y
        if fill is not None:
            c.setFillColor(fill)
            c.rect(x0, y - height, table_w, height, stroke=0, fill=1)
        cx = x0
        c.setFont(fonts.bold() if bold_row else fonts.regular(), 8.5)
        for i, cell in enumerate(cells):
            c.setFillColor(C_INK if cell is not None else C_BLANK)
            text = cell if cell is not None else ""
            c.drawCentredString(cx + widths[i] / 2, y - height + 2.6 * mm, text)
            if cell is None:
                blank_line(c, cx + widths[i] * 0.2, y - height + 2.1 * mm, widths[i] * 0.6)
            cx += widths[i]
        c.setStrokeColor(C_LINE)
        c.setLineWidth(0.5)
        c.line(x0, y - height, x0 + table_w, y - height)
        y -= height

    row(cols, bold_row=True, fill=C_ACCENT_LT)

    for nine_idx, (lo, hi) in enumerate(((1, 9), (10, 18))):
        holes = [h for h in course.holes if lo <= h.hole <= hi]
        if not holes:
            continue
        nine_key = holes[0].nine
        c.setFont(fonts.bold(), 8.5)
        c.setFillColor(C_ACCENT)
        c.drawString(x0 + 2, y - 5 * mm, f"{course.nine_name(nine_key)}  ({'OUT' if nine_idx == 0 else 'IN'})")
        y -= 6.5 * mm

        for h in holes:
            row(
                [str(h.hole), fmt(h.par), fmt(h.handicap)]
                + [fmt(h.tees.get(k)) for k in tee_keys]
                + [None]
            )
        row(
            ["합계", fmt(course.par_total(holes)), ""]
            + [fmt(course.tee_total(k, holes)) for k in tee_keys]
            + [None],
            bold_row=True,
            fill=HexColor("#F3F7F1"),
        )

    row(
        ["TOTAL", fmt(course.par_total()), ""]
        + [fmt(course.tee_total(k)) for k in tee_keys]
        + [None],
        bold_row=True,
        fill=C_ACCENT_LT,
    )

    y -= 8 * mm
    c.setFont(fonts.bold(), 9)
    c.setFillColor(C_INK)
    c.drawString(x0, y, "보기플레이 목표 스코어")
    y -= 13
    target = int(course.player.get("target_score", 90))
    par_total = _declared_par(course)
    n_holes = _declared_holes(course)
    all_bogey = par_total + n_holes
    gap = all_bogey - target
    if gap > 0:
        how = f"여기서 파를 {gap}개 잡으면 목표 {target}타"
    elif gap == 0:
        how = f"전 홀 보기가 곧 목표 {target}타"
    else:
        how = f"목표 {target}타는 전 홀 보기보다 {-gap}타 여유가 있는 스코어"
    para(
        c,
        f"{n_holes}홀 전 홀 보기 = {all_bogey}타. {how}입니다. 더블보기 하나가 파 하나를 지우므로, "
        f"각 홀 페이지의 '보기 플랜'은 파를 노리는 배분이 아니라 더블보기를 지우는 배분입니다.",
        x0, y, table_w, size=8.5, leading=11.5,
    )
    _footer(c, course.meta.get("name", ""))
    c.showPage()


def strategy_page(c: Canvas, course: Course) -> None:
    _page_header(c, "보기플레이 기본 전략", course.meta.get("slogan", ""))
    x0, w = MARGIN, PAGE_W - 2 * MARGIN
    y = PAGE_H - 34 * mm

    # 코스별 보정 항목은 데이터(strategy.course_notes)에서 가져오고, 없으면 건너뛴다.
    blocks: list[tuple[str, list[str]]] = [
        (
            "더블보기를 만드는 3가지만 지운다",
            [
                "OB · 해저드 — 티샷은 '넓은 쪽'이 아니라 '벌타 없는 쪽'을 본다. 코너 공략 금지.",
                "그린 못 미친 벙커 — 애매하면 한 클럽 길게 잡고 그린 뒤 에지를 노린다.",
                "3퍼트 — 첫 퍼트는 홀 지나 1m. 홀 못 미치는 퍼트가 3퍼트를 만든다.",
            ],
        ),
        (
            "파를 버리는 대신 보기를 확보하는 배분",
            [
                "파4: 티샷 → 100m 안쪽으로 레이업 → 웨지 → 2퍼트. 세컨 그린 직접 공략은 150m 이내일 때만.",
                "파5: 3온을 목표로 두지 않는다. 세컨을 그린 100m 앞 평지로 보내는 것이 유일한 목표.",
                "파3: 핀이 아니라 그린 중앙. 짧은 쪽 미스가 항상 긴 쪽 미스보다 낫다.",
            ],
        ),
    ]

    course_notes = [str(s) for s in (course.strategy.get("course_notes") or [])]
    if course_notes:
        blocks.append((str(course.strategy.get("course_notes_title", "이 코스 보정")), course_notes))

    blocks.append(
        (
            "라운드 중 규칙",
            [
                "한 홀에서 같은 미스를 두 번 하면, 그 홀은 그 클럽을 봉인한다.",
                "더블보기 이상이 난 다음 홀은 무조건 안전 배분으로 되돌린다.",
                "티잉그라운드에서 목표를 소리 내어 정하고 스윙한다. 정하지 않은 스윙이 OB를 만든다.",
            ],
        )
    )

    sections = [(f"{i}. {title}", items) for i, (title, items) in enumerate(blocks, 1)]

    for title, items in sections:
        c.setFont(fonts.bold(), 10.5)
        c.setFillColor(C_ACCENT)
        c.drawString(x0, y, title)
        y -= 15
        for item in items:
            y = bullet(c, item, x0 + 2, y, w - 2, size=8.7, leading=11.5) - 4
        y -= 8

    # 내 클럽 거리표
    clubs = course.player.get("clubs") or []
    if clubs:
        c.setFont(fonts.bold(), 10.5)
        c.setFillColor(C_ACCENT)
        c.drawString(x0, y, f"내 클럽 거리 ({_data_ref(course)} 의 player.clubs)")
        y -= 8
        per_row = 6
        cell_w = w / per_row
        cell_h = 14 * mm
        for i, club in enumerate(clubs):
            col, rowi = i % per_row, i // per_row
            cx = x0 + col * cell_w
            cy = y - (rowi + 1) * cell_h
            c.setStrokeColor(C_LINE)
            c.setLineWidth(0.5)
            c.setFillColor(HexColor("#FAFCF9"))
            c.rect(cx, cy, cell_w - 2, cell_h - 2, stroke=1, fill=1)
            mid = cx + (cell_w - 2) / 2
            c.setFillColor(C_MUTED)
            c.setFont(fonts.regular(), 7.5)
            c.drawCentredString(mid, cy + cell_h - 6 * mm, str(club["name"]))
            c.setFillColor(C_INK)
            c.setFont(fonts.bold(), 12)
            c.drawCentredString(mid, cy + 3.4 * mm, f"{club['dist']:.0f}m")
        y -= ((len(clubs) - 1) // per_row + 1) * cell_h + 12 * mm

    # 티오프 전 체크리스트
    c.setFont(fonts.bold(), 10.5)
    c.setFillColor(C_ACCENT)
    c.drawString(x0, y, "티오프 전 확인")
    y -= 15
    checks = [
        "오늘의 목표는 스코어가 아니라 '더블보기 0개'",
        "드라이버를 뺄 홀 3개를 미리 정해 둔다 (핸디캡 1·2·3번 홀)",
        "그린 스피드는 첫 홀 첫 퍼트로 측정 — 그 전까지 라인보다 거리",
        "OB 티 위치와 로컬룰(캐디에게 확인)",
    ]
    for item in checks:
        c.setStrokeColor(C_LINE)
        c.setLineWidth(0.7)
        c.rect(x0 + 1, y - 2, 8, 8, stroke=1, fill=0)
        y = para(c, item, x0 + 14, y, w - 14, size=8.7, leading=11.5) - 4

    _footer(c, course.meta.get("name", ""))
    c.showPage()


def single_strategy_page(c: Canvas, course: Course) -> None:
    _page_header(c, "싱글플레이 전략", "한 자리 핸디로 가는 길")
    x0, w = MARGIN, PAGE_W - 2 * MARGIN
    y = PAGE_H - 34 * mm

    par_total = _declared_par(course)
    n_holes = _declared_holes(course)

    # 싱글 기준선: 파 + 9 (한 자리 핸디의 상한)
    target = par_total + 9
    over = target - par_total
    if 0 <= over <= n_holes:
        breakdown = f"'파 {n_holes - over}개 + 보기 {over}개 + 더블보기 0개'"
    else:
        breakdown = "'보기를 최소로, 더블보기는 0개'"
    y = para(
        c,
        f"싱글은 버디를 잡아서 만들어지지 않습니다. 파 {par_total} 코스에서 {target}타는 "
        f"{breakdown} 로 나오는 숫자입니다. 아래 항목은 전부 '파를 지키는' 것이지 "
        "'버디를 만드는' 것이 아닙니다.",
        x0, y, w, size=8.7, leading=11.5,
    )
    y -= 10

    sections = [
        (
            "1. 목표는 스코어가 아니라 지표",
            [
                "GIR(레귤러 온) 7~9개 — 싱글과 보기플레이를 가르는 단 하나의 지표.",
                "페어웨이 안착 8홀 이상 — 러프에서 그린을 노리면 GIR 이 절반으로 떨어진다.",
                "3퍼트 1개 이하, 파세이브(업앤다운) 50% 이상.",
                "이 네 개를 라운드마다 적으면, 어디서 타수가 새는지 두 라운드면 보인다.",
            ],
        ),
        (
            "2. 티샷 — 드라이버를 '고르는' 것이 실력",
            [
                "드라이버는 페어웨이가 넓고 OB·해저드가 없는 홀에서만. 나머지는 우드·유틸.",
                "티잉그라운드는 위험한 쪽 끝에 서서 안전한 쪽으로 조준선을 연다.",
                "300m 이하 파4에서 드라이버로 70m 를 남기면 오히려 어렵다. 100m 를 남긴다.",
            ],
        ),
        (
            "3. 세컨 — 핀이 아니라 그린 중앙 + 안전한 쪽",
            [
                "기본 조준은 그린 중앙. 거기서 안전한 쪽으로 4m 만 옮긴다.",
                "핀이 에지 5m 안쪽에 꽂혔으면 무조건 무시. 숏사이드가 보기를 만든다.",
                "그린 뒤가 트인 홀에서만 한 클럽 길게. 앞에 벙커·해저드면 무조건 길게.",
                "라이가 나쁘면 그 시점에 목표를 그린에서 '그린 앞 안전지대'로 내린다.",
            ],
        ),
        (
            "4. 파5 — 2온은 세 조건이 다 맞을 때만",
            [
                "① 티샷이 페어웨이  ② 남은 거리가 평소 최장 클럽 안쪽  ③ 그린 앞이 트여 있음.",
                "하나라도 어긋나면 100m 남기고 레이업. 2온 실패의 대가는 보기가 아니라 더블이다.",
                "레이업은 '어중간한 60m'가 아니라 '풀스윙 웨지 거리'로 맞춘다.",
            ],
        ),
        (
            "5. 숏게임 · 퍼팅 — 파를 지키는 마지막 구간",
            [
                "굴릴 수 있으면 굴린다. 로브샷은 넘길 것이 있을 때만 쓰는 마지막 수단.",
                "60m 이내에서 두 번에 끝내는 확률이 싱글을 만든다. 붙이는 게 아니라 '2퍼트 안에'.",
                "롱퍼트는 라인보다 거리. 3m 이내는 라인. 홀 지나 1m 를 항상 지킨다.",
            ],
        ),
    ]

    for title, items in sections:
        c.setFont(fonts.bold(), 10.5)
        c.setFillColor(C_ACCENT)
        c.drawString(x0, y, title)
        y -= 15
        for item in items:
            y = bullet(c, item, x0 + 2, y, w - 2, size=8.7, leading=11.5) - 4
        y -= 7

    # 지표 기록표
    c.setFont(fonts.bold(), 10.5)
    c.setFillColor(C_ACCENT)
    c.drawString(x0, y, "라운드별 지표 기록")
    y -= 8

    cols = ["날짜", "스코어", "GIR", "페어웨이", "퍼트", "업앤다운", "더블+"]
    widths = [w * 0.22] + [w * 0.13] * 6
    row_h = 8 * mm
    for r in range(6):
        ry = y - r * row_h
        cx = x0
        for i, col in enumerate(cols):
            c.setStrokeColor(C_LINE)
            c.setLineWidth(0.5)
            c.setFillColor(C_ACCENT_LT if r == 0 else HexColor("#FFFFFF"))
            c.rect(cx, ry - row_h, widths[i], row_h, stroke=1, fill=1)
            if r == 0:
                c.setFont(fonts.bold(), 8)
                c.setFillColor(C_INK)
                c.drawCentredString(cx + widths[i] / 2, ry - row_h + 2.6 * mm, col)
            cx += widths[i]

    _footer(c, course.meta.get("name", ""))
    c.showPage()


def hole_page(c: Canvas, course: Course, hole: Hole, tee_key: str, level: str = "bogey") -> None:
    nine = course.nine_name(hole.nine)
    half = "OUT" if hole.hole <= 9 else "IN"
    # 코스 이름 자체가 'OUT COURSE' 같은 형태면 OUT/IN 을 덧붙이지 않는다.
    subtitle = nine if half in nine.upper() else f"{nine} · {half}"
    _page_header(c, f"{hole.hole}번홀", subtitle)

    # 상단 파/핸디캡/거리 요약 바
    bar_y = PAGE_H - 40 * mm
    bar_h = 16 * mm
    c.setFillColor(C_ACCENT_LT)
    c.roundRect(MARGIN, bar_y, PAGE_W - 2 * MARGIN, bar_h, 3, stroke=0, fill=1)

    cells = [("PAR", fmt(hole.par)), ("HDCP", fmt(hole.handicap))]
    cells += [(t["label"], fmt(hole.tees.get(t["key"]), "m")) for t in course.tees]
    cw = (PAGE_W - 2 * MARGIN) / len(cells)
    for i, (label, value) in enumerate(cells):
        cx = MARGIN + i * cw + cw / 2
        c.setFont(fonts.regular(), 7)
        c.setFillColor(C_MUTED)
        c.drawCentredString(cx, bar_y + bar_h - 6 * mm, label)
        if value is None:
            blank_line(c, cx - cw * 0.28, bar_y + 4 * mm, cw * 0.56)
        else:
            c.setFont(fonts.bold(), 13)
            c.setFillColor(C_INK)
            c.drawCentredString(cx, bar_y + 3.6 * mm, value)

    # 좌: 도면 / 우: 텍스트. 실제 코스안내도가 있으면 왼쪽 단을 넓혀 위아래로 쌓는다.
    ref_tee = str(course.meta.get("hazard_ref_tee") or tee_key)
    col_gap = 8 * mm
    img_path = _image_path(hole)
    left_w = (PAGE_W - 2 * MARGIN) * (0.42 if img_path else 0.33)
    text_x = MARGIN + left_w + col_gap
    text_w = PAGE_W - MARGIN - text_x
    col_h = 172 * mm
    diag_y = bar_y - 8 * mm - col_h

    if img_path:
        img_h = col_h * 0.52
        used = _draw_course_map(c, MARGIN, diag_y + col_h - img_h, left_w, img_h, img_path)
        sch_h = col_h - used - 8 * mm
        diagram.draw_hole(c, MARGIN, diag_y, left_w, sch_h, hole, tee_key,
                          tees=course.tees, ref_tee=ref_tee)
    else:
        diagram.draw_hole(c, MARGIN, diag_y, left_w, col_h, hole, tee_key,
                          tees=course.tees, ref_tee=ref_tee)

    y = bar_y - 10 * mm

    # 그린 정보
    g = hole.green
    y = _sub(c, "그린", text_x, y)

    # 그린 상세도가 있으면 오른쪽에 붙이고, 글은 왼쪽 폭만 쓴다.
    green_img = _resolve(hole.green_image)
    txt_w = text_w
    if green_img:
        gi_w = min(text_w * 0.42, 42 * mm)
        gi_h = _draw_green_map(c, text_x + text_w - gi_w, y, gi_w, 40 * mm, green_img)
        txt_w = text_w - gi_w - 5 * mm

    green_bits = []
    if g.get("depth"):
        green_bits.append(f"깊이 {g['depth']}m")
    if g.get("width"):
        green_bits.append(f"폭 {g['width']}m")
    if g.get("tier"):
        green_bits.append(str(g["tier"]))
    if green_bits:
        y = para(c, " · ".join(green_bits), text_x, y, txt_w, size=8.3, leading=11)
    if g.get("break"):
        y = para(c, f"브레이크: {g['break']}", text_x, y, txt_w, size=8.3, leading=11)
    if not green_bits and not g.get("break"):
        for _ in range(2):
            blank_line(c, text_x, y + 2, txt_w)
            y -= 12
    if green_img:
        y = min(y, gi_h) - 4
    y -= 4
    y = _green_fcb_table(c, course, hole, text_x, y, txt_w)
    y -= 8

    # 해저드
    y = _sub(c, "해저드 · 위험구역", text_x, y)
    if hole.hazards:
        for hz in hole.hazards:
            color = C_RED if hz.type in ("ob", "water") else C_INK
            y = bullet(c, hz.label(), text_x, y, text_w, size=8.3, leading=10.8, color=color) - 2
    else:
        for _ in range(3):
            blank_line(c, text_x, y + 2, text_w)
            y -= 12
    y -= 6

    # 공략 포인트
    keys = general_keys(hole)
    y = _sub(c, "공략 포인트", text_x, y)
    if keys:
        for k in keys:
            y = bullet(c, k, text_x, y, text_w, size=8.3, leading=10.8) - 2
    else:
        for _ in range(3):
            blank_line(c, text_x, y + 2, text_w)
            y -= 12
    y -= 6

    # 샷 플랜 — level 에 따라 보기 / 싱글 / 둘 다
    for kind in _plan_kinds(level):
        if kind == "bogey":
            steps = bogey_plan(hole, course.player, tee_key)
            manual = bool(hole.bogey_plan)
            title = f"보기 플랜 (목표 {hole.par + 1}타)" if hole.par else "보기 플랜"
        else:
            steps = single_plan(hole, course.player, tee_key)
            manual = bool(hole.single_plan)
            title = f"싱글 플랜 (목표 {hole.par}타)" if hole.par else "싱글 플랜"

        y = _sub(c, title, text_x, y)
        if steps:
            for i, step in enumerate(steps, 1):
                y = bullet(c, step, text_x, y, text_w, size=8.3, leading=10.8, marker=f"{i}") - 2
            if not manual:
                c.setFont(fonts.regular(), 6.5)
                c.setFillColor(C_MUTED)
                c.drawString(text_x, y, "* 거리와 클럽 설정값에서 자동 계산된 배분입니다.")
                y -= 10
        else:
            for _ in range(4):
                blank_line(c, text_x, y + 2, text_w)
                y -= 12
        y -= 6

    # 메모
    y = _sub(c, "라운드 메모", text_x, y)
    if hole.note:
        y = para(c, hole.note, text_x, y, text_w, size=8.3, leading=11)
    while y > diag_y + 6:
        blank_line(c, text_x, y + 2, text_w)
        y -= 12

    _score_boxes(c, MARGIN, diag_y - 12 * mm, PAGE_W - 2 * MARGIN)
    _footer(c, f"{course.meta.get('name', '')} · {nine} {hole.hole}번홀")
    c.showPage()


def log_page(c: Canvas, course: Course) -> None:
    _page_header(c, "라운드 기록", "홀별 스코어 · 퍼트 · 페어웨이 안착")
    x0 = MARGIN
    w = PAGE_W - 2 * MARGIN
    y = PAGE_H - 32 * mm

    for label in ("1라운드", "2라운드"):
        c.setFont(fonts.bold(), 10)
        c.setFillColor(C_ACCENT)
        c.drawString(x0, y, label)
        blank_line(c, x0 + 20 * mm, y, 50 * mm)  # 날짜 기입란
        c.setFont(fonts.regular(), 7)
        c.setFillColor(C_MUTED)
        c.drawString(x0 + 20 * mm, y + 4, "날짜 / 동반자")
        y = _round_grid(c, course, x0, y - 6, w) - 14 * mm
    c.setFont(fonts.bold(), 10)
    c.setFillColor(C_ACCENT)
    c.drawString(x0, y, "라운드 후 3줄 회고")
    y -= 16
    for label in ("잘된 것", "무너진 지점", "다음 라운드에서 바꿀 것 한 가지"):
        c.setFont(fonts.regular(), 8.5)
        c.setFillColor(C_MUTED)
        c.drawString(x0, y, label)
        blank_line(c, x0 + 45 * mm, y, w - 45 * mm)
        y -= 16

    _footer(c, course.meta.get("name", ""))
    c.showPage()


# --------------------------------------------------------------------------
# 공통 파츠
# --------------------------------------------------------------------------

def _resolve(raw: str) -> str | None:
    """저장소 기준 상대경로를 절대경로로. 파일이 없으면 None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(_REPO_ROOT, raw)
    return path if os.path.isfile(path) else None


def _image_path(hole: Hole) -> str | None:
    """홀 전체 코스안내도 이미지 경로."""
    return _resolve(hole.image)


def _draw_course_map(c: Canvas, x: float, y: float, w: float, h: float, path: str) -> float:
    """코스안내도 이미지를 비율 유지해 넣고, 실제로 사용한 높이를 돌려준다."""
    try:
        reader = ImageReader(path)
        iw, ih = reader.getSize()
    except Exception as exc:  # 손상된 파일 등
        c.setFont(fonts.regular(), 7)
        c.setFillColor(C_RED)
        c.drawString(x, y + h - 10, f"이미지를 읽을 수 없습니다: {os.path.basename(path)} ({exc})")
        return h

    cap_h = 9
    box_h = h - cap_h
    scale = min(w / iw, box_h / ih)
    dw, dh = iw * scale, ih * scale
    dx = x + (w - dw) / 2
    dy = y + h - dh

    c.drawImage(reader, dx, dy, dw, dh, preserveAspectRatio=True, anchor="n", mask="auto")
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.6)
    c.rect(dx, dy, dw, dh, stroke=1, fill=0)

    c.setFont(fonts.regular(), 6)
    c.setFillColor(C_MUTED)
    c.drawString(x + 1, dy - 7, "실제 코스안내도 (골프장 제공)")
    return dh + cap_h


def _green_fcb_table(c: Canvas, course: Course, hole: Hole, x: float, y: float, w: float) -> float:
    """그린 앞 / 중앙 / 뒤 거리표 — 실제 야디지북의 F·C·B 표.

    티 거리는 관례상 그린 중앙까지이므로, 그린 깊이의 절반을 앞뒤로 더한다.
    """
    depth = hole.green.get("depth")
    if not depth or not hole.known:
        return y

    half = float(depth) / 2
    rows = [("앞", -half), ("중앙", 0.0), ("뒤", +half)]
    tees = course.tees

    label_w = 13 * mm
    cell_w = (w - label_w) / max(1, len(tees))
    row_h = 5.6 * mm

    # 헤더
    cx = x + label_w
    c.setFont(fonts.regular(), 6.5)
    for tee in tees:
        c.setFillColor(HexColor(str(tee.get("color", "#000000"))))
        c.circle(cx + 4, y + 2.2, 1.9, stroke=0, fill=1)
        c.setFillColor(C_MUTED)
        c.drawString(cx + 8, y, str(tee.get("label", tee["key"])))
        cx += cell_w
    y -= 4

    for name, delta in rows:
        c.setStrokeColor(C_LINE)
        c.setLineWidth(0.5)
        c.rect(x, y - row_h, w, row_h, stroke=1, fill=0)
        c.setFont(fonts.bold(), 7.5)
        c.setFillColor(C_ACCENT)
        c.drawString(x + 3, y - row_h + 1.9 * mm, name)
        cx = x + label_w
        for tee in tees:
            base = hole.tees.get(tee["key"])
            c.setFont(fonts.bold(), 8.5)
            c.setFillColor(C_INK if base is not None else C_BLANK)
            text = f"{base + delta:.0f}" if base is not None else "·"
            c.drawCentredString(cx + cell_w / 2, y - row_h + 1.9 * mm, text)
            cx += cell_w
        y -= row_h
    return y


def _draw_green_map(c: Canvas, x: float, y: float, w: float, max_h: float, path: str) -> float:
    """그린 상세도를 (x, y) 오른쪽 위 기준으로 넣고, 이미지 아래쪽 y를 돌려준다."""
    try:
        reader = ImageReader(path)
        iw, ih = reader.getSize()
    except Exception:
        return y

    scale = min(w / iw, max_h / ih)
    dw, dh = iw * scale, ih * scale
    dy = y + 6 - dh
    c.drawImage(reader, x, dy, dw, dh, preserveAspectRatio=True, anchor="n", mask="auto")
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.5)
    c.rect(x, dy, dw, dh, stroke=1, fill=0)
    c.setFont(fonts.regular(), 5.5)
    c.setFillColor(C_MUTED)
    c.drawString(x, dy - 6, "그린 상세도 (골프장 제공)")
    return dy - 10


def _round_grid(c: Canvas, course: Course, x0: float, y: float, w: float) -> float:
    """18홀 기록 그리드를 그리고 아래쪽 y를 돌려준다."""
    rows = ["홀", "파", "스코어", "퍼트", "FW", "벌타"]
    label_w = 20 * mm
    cell_w = (w - label_w) / 18
    row_h = 8 * mm

    for r, label in enumerate(rows):
        ry = y - r * row_h
        c.setFillColor(C_ACCENT_LT if r == 0 else HexColor("#FFFFFF"))
        c.rect(x0, ry - row_h, w, row_h, stroke=0, fill=1)
        c.setStrokeColor(C_LINE)
        c.setLineWidth(0.5)
        c.rect(x0, ry - row_h, label_w, row_h, stroke=1, fill=0)
        c.setFont(fonts.bold(), 8)
        c.setFillColor(C_INK)
        c.drawCentredString(x0 + label_w / 2, ry - row_h + 2.6 * mm, label)
        for i in range(18):
            cx = x0 + label_w + i * cell_w
            c.rect(cx, ry - row_h, cell_w, row_h, stroke=1, fill=0)
            if r == 0:
                c.setFont(fonts.bold(), 8)
                c.setFillColor(C_INK)
                c.drawCentredString(cx + cell_w / 2, ry - row_h + 2.6 * mm, str(i + 1))
            elif r == 1:
                p = course.holes[i].par if i < len(course.holes) else None
                c.setFont(fonts.regular(), 8)
                c.setFillColor(C_MUTED if p else C_BLANK)
                c.drawCentredString(cx + cell_w / 2, ry - row_h + 2.6 * mm, str(p) if p else "·")

    return y - len(rows) * row_h


def _page_header(c: Canvas, title: str, subtitle: str) -> None:
    c.setFillColor(C_ACCENT)
    c.rect(0, PAGE_H - 20 * mm, PAGE_W, 20 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont(fonts.bold(), 15)
    c.drawString(MARGIN, PAGE_H - 14 * mm, title)
    if subtitle:
        c.setFont(fonts.regular(), 9.5)
        c.setFillColor(HexColor("#CFE3CB"))
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 13.5 * mm, subtitle)


def _sub(c: Canvas, title: str, x: float, y: float) -> float:
    c.setFont(fonts.bold(), 9)
    c.setFillColor(C_ACCENT)
    c.drawString(x, y, title)
    y -= 4
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.6)
    c.line(x, y, x + 18, y)
    return y - 11


def _score_boxes(c: Canvas, x: float, y: float, w: float) -> None:
    labels = ["1R", "2R", "3R", "4R"]
    fields = ["스코어", "퍼트", "FW", "벌타"]
    cell_w = w / (len(fields) + 1)
    row_h = 5.4 * mm

    c.setFont(fonts.regular(), 7)
    for r, label in enumerate([""] + labels):
        ry = y - r * row_h
        for i, field_name in enumerate([""] + fields):
            cx = x + i * cell_w
            c.setStrokeColor(C_LINE)
            c.setLineWidth(0.5)
            c.setFillColor(C_ACCENT_LT if r == 0 or i == 0 else HexColor("#FFFFFF"))
            c.rect(cx, ry - row_h, cell_w, row_h, stroke=1, fill=1)
            text = field_name if r == 0 else (label if i == 0 else "")
            if text:
                c.setFillColor(C_INK)
                c.setFont(fonts.bold(), 7)
                c.drawCentredString(cx + cell_w / 2, ry - row_h + 1.8 * mm, text)


def _footer(c: Canvas, text: str) -> None:
    c.setFont(fonts.regular(), 7)
    c.setFillColor(C_MUTED)
    c.drawString(MARGIN, 10 * mm, text)
    c.drawRightString(PAGE_W - MARGIN, 10 * mm, str(c.getPageNumber()))


# --------------------------------------------------------------------------

def build(course: Course, out_path: str, tee_key: str, level: str = "bogey") -> None:
    c = Canvas(out_path, pagesize=A4)
    meta = course.meta
    c.setTitle(f"{meta.get('name', '')} {meta.get('subtitle', '')}")
    c.setAuthor(meta.get("name", ""))
    c.setSubject(meta.get("slogan", ""))

    cover(c, course)
    scorecard(c, course)
    strategy_page(c, course)
    single_strategy_page(c, course)
    for hole in course.holes:
        hole_page(c, course, hole, tee_key, level)
    log_page(c, course)
    c.save()
