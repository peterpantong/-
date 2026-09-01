"""코스 데이터 로딩 · 검증 · 파생값 계산."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# 데이터가 비어 있을 때 도면을 그리기 위한 기본 홀 길이(m).
DEFAULT_LENGTH_BY_PAR = {3: 160, 4: 350, 5: 480}
FALLBACK_LENGTH = 350

SHAPES = {"straight", "dogleg_left", "dogleg_right"}
ELEVATIONS = {"flat", "uphill", "downhill"}


@dataclass
class Hazard:
    type: str  # bunker | water | ob | tree | slope
    side: str = "right"  # left | right | center | greenside_left | ...
    start: float | None = None  # 티에서의 거리(m)
    end: float | None = None
    note: str = ""

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Hazard":
        return cls(
            type=str(raw.get("type", "bunker")),
            side=str(raw.get("side", "right")),
            start=_num(raw.get("start", raw.get("from"))),
            end=_num(raw.get("end", raw.get("to"))),
            note=str(raw.get("note", "")),
        )

    def label(self) -> str:
        names = {
            "bunker": "벙커",
            "water": "해저드",
            "ob": "OB",
            "tree": "나무",
            "slope": "경사",
        }
        sides = {
            "left": "좌",
            "right": "우",
            "center": "중앙",
            "front": "그린 앞",
            "back": "그린 뒤",
            "greenside_left": "그린 좌",
            "greenside_right": "그린 우",
        }
        head = f"{sides.get(self.side, self.side)} {names.get(self.type, self.type)}"
        if self.start is not None and self.end is not None:
            head += f" {self.start:.0f}~{self.end:.0f}m"
        elif self.start is not None:
            head += f" {self.start:.0f}m"
        return head + (f" · {self.note}" if self.note else "")


@dataclass
class Hole:
    hole: int
    nine: str
    par: int | None
    handicap: int | None
    shape: str
    elevation: str
    tees: dict[str, float | None]
    green: dict[str, Any]
    hazards: list[Hazard]
    keys: list[str]
    bogey_plan: list[str]
    note: str
    image: str = ""  # 골프장이 제공하는 실제 코스안내도 이미지 경로

    @property
    def known(self) -> bool:
        """실제 거리 데이터가 들어 있는가."""
        return any(v is not None for v in self.tees.values())

    def length(self, tee_key: str | None = None) -> float:
        """도면·플랜 계산에 쓸 홀 길이(m). 데이터가 없으면 par 기준 기본값."""
        if tee_key and self.tees.get(tee_key) is not None:
            return float(self.tees[tee_key])
        for v in self.tees.values():
            if v is not None:
                return float(v)
        return DEFAULT_LENGTH_BY_PAR.get(self.par or 0, FALLBACK_LENGTH)

    @property
    def nine_index(self) -> int:
        return 0 if self.hole <= 9 else 1


@dataclass
class Course:
    meta: dict[str, Any]
    tees: list[dict[str, Any]]
    player: dict[str, Any]
    holes: list[Hole] = field(default_factory=list)
    strategy: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""  # 어떤 JSON 에서 왔는지 (안내 문구에 표시)

    @property
    def complete(self) -> bool:
        return all(h.known and h.par for h in self.holes)

    def nine_name(self, key: str) -> str:
        for n in self.meta.get("nines", []):
            if n.get("key") == key:
                return str(n.get("name", key))
        return key

    def tee_total(self, tee_key: str, holes: list[Hole] | None = None) -> float | None:
        holes = self.holes if holes is None else holes
        vals = [h.tees.get(tee_key) for h in holes]
        if any(v is None for v in vals) or not vals:
            return None
        return float(sum(vals))  # type: ignore[arg-type]

    def par_total(self, holes: list[Hole] | None = None) -> int | None:
        holes = self.holes if holes is None else holes
        vals = [h.par for h in holes]
        if any(v is None for v in vals) or not vals:
            return None
        return int(sum(vals))  # type: ignore[arg-type]


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(path: str) -> Course:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    meta = raw.get("course", {})
    tees = raw.get("tees", [])
    if not tees:
        raise ValueError("데이터에 tees 정의가 없습니다.")
    tee_keys = [t["key"] for t in tees]

    holes: list[Hole] = []
    for item in raw.get("holes", []):
        shape = str(item.get("shape", "straight"))
        if shape not in SHAPES:
            raise ValueError(f"{item.get('hole')}번홀: 알 수 없는 shape '{shape}'")
        elevation = str(item.get("elevation", "flat"))
        if elevation not in ELEVATIONS:
            raise ValueError(f"{item.get('hole')}번홀: 알 수 없는 elevation '{elevation}'")

        par = item.get("par")
        if par is not None and int(par) not in (3, 4, 5, 6):
            raise ValueError(f"{item.get('hole')}번홀: par 값이 이상합니다 ({par})")

        holes.append(
            Hole(
                hole=int(item["hole"]),
                nine=str(item.get("nine", "out")),
                par=None if par is None else int(par),
                handicap=None if item.get("handicap") is None else int(item["handicap"]),
                shape=shape,
                elevation=elevation,
                tees={k: _num(item.get("tees", {}).get(k)) for k in tee_keys},
                green=item.get("green", {}) or {},
                hazards=[Hazard.parse(h) for h in item.get("hazards", [])],
                keys=[str(s) for s in item.get("keys", [])],
                bogey_plan=[str(s) for s in item.get("bogey_plan", [])],
                note=str(item.get("note", "")),
                image=str(item.get("image", "") or ""),
            )
        )

    holes.sort(key=lambda h: h.hole)
    numbers = [h.hole for h in holes]
    if numbers != list(range(1, len(holes) + 1)):
        raise ValueError(f"홀 번호가 1..{len(holes)} 연속이 아닙니다: {numbers}")

    return Course(
        meta=meta,
        tees=tees,
        player=raw.get("player", {}),
        holes=holes,
        strategy=raw.get("strategy", {}) or {},
        source_path=path,
    )


# --------------------------------------------------------------------------
# 보기플레이 플랜 자동 생성
# --------------------------------------------------------------------------

def pick_club(player: dict[str, Any], dist: float) -> str:
    """거리에 가장 가까운 클럽 이름."""
    clubs = player.get("clubs") or []
    if not clubs:
        return f"{dist:.0f}m 클럽"
    best = min(clubs, key=lambda c: abs(float(c["dist"]) - dist))
    return str(best["name"])


def _euro(word: str) -> str:
    """'~로 / ~으로' 조사를 받침에 맞춰 붙인다. (아이언 -> 아이언으로, 웨지 -> 웨지로)"""
    if not word:
        return word
    last = word[-1]
    if "가" <= last <= "힣":
        jong = (ord(last) - 0xAC00) % 28
        return word + ("로" if jong in (0, 8) else "으로")  # 받침 없음 또는 ㄹ
    return word + "로"


def club_with(player: dict[str, Any], dist: float) -> str:
    """'7번 아이언으로' 형태의 문구."""
    return _euro(pick_club(player, dist))


def bogey_plan(hole: Hole, player: dict[str, Any], tee_key: str) -> list[str]:
    """파별 '보기로 막는' 샷 배분을 거리에서 역산한다.

    직접 적어 넣은 bogey_plan 이 있으면 그것을 그대로 쓴다.
    """
    if hole.bogey_plan:
        return hole.bogey_plan
    if not hole.par:
        return []

    total = hole.length(tee_key)
    driver = float(next((c["dist"] for c in player.get("clubs", []) if "드라이버" in c["name"]), 200))
    wedge_zone = 90.0  # 풀스윙 웨지가 남는 거리대

    if hole.par == 3:
        return [
            f"티샷 {total:.0f}m — {club_with(player, total)} 그린 중앙(핀 무시)",
            "미스는 그린 앞 또는 넓은 쪽 에지로. 뒤·벙커·해저드 쪽은 금지",
            "온그린 2퍼트 = 파, 에지에서 굴려 붙이고 1퍼트 = 보기",
        ]

    if hole.par == 4:
        # 그린 70m 안쪽까지 굴러가 버리는 티샷은 의미가 없다
        drive = min(driver, max(140.0, total - 70.0))
        rest = total - drive
        longest = max((float(c["dist"]) for c in player.get("clubs", [])), default=200.0)
        if rest <= min(150.0, longest):
            return [
                f"티샷 {drive:.0f}m — 페어웨이 유지 최우선. 거리보다 방향",
                f"세컨 {rest:.0f}m — {club_with(player, rest)} 그린 중앙. 짧으면 그린 앞 안전지대",
                "어프로치 붙이고 2퍼트 이내 = 보기",
            ]
        layup = rest - wedge_zone
        return [
            f"티샷 {drive:.0f}m — 페어웨이 폭이 넓은 지점까지만. 거리보다 방향",
            f"세컨 남은거리 {rest:.0f}m — {club_with(player, layup)} {layup:.0f}m 보내 그린 {wedge_zone:.0f}m 앞까지 레이업",
            f"서드 {wedge_zone:.0f}m — {club_with(player, wedge_zone)} 그린 중앙",
            "2퍼트로 보기. 온그린 되면 파 시도",
        ]

    # par 5 이상
    drive = min(driver, total * 0.42)
    layup_target = 100.0
    second = max(60.0, total - drive - layup_target)
    return [
        f"티샷 {drive:.0f}m — OB·해저드 없는 쪽으로. 3온은 애초에 목표가 아님",
        f"세컨 {second:.0f}m — {club_with(player, second)} 그린 {layup_target:.0f}m 앞 평지까지",
        f"서드 {layup_target:.0f}m — {club_with(player, layup_target)} 그린 중앙",
        "2퍼트 보기. 세컨이 잘 맞으면 웨지로 파 노림",
    ]


def general_keys(hole: Hole) -> list[str]:
    """홀 데이터에서 자동으로 뽑는 공략 포인트."""
    out: list[str] = list(hole.keys)
    if hole.shape == "dogleg_left":
        out.append("좌 도그렉 — 페어웨이 우측에서 코너를 보고 공략")
    elif hole.shape == "dogleg_right":
        out.append("우 도그렉 — 페어웨이 좌측에서 코너를 보고 공략")
    if hole.elevation == "uphill":
        out.append("오르막 — 한 클럽 이상 길게, 그린은 짧게 떨어짐")
    elif hole.elevation == "downhill":
        out.append("내리막 — 한 클럽 짧게, 런 감안")
    for h in hole.hazards:
        if h.type == "ob":
            out.append(f"{h.label()} — 반대쪽 티 끝에 서서 안쪽으로 조준")
    return out
