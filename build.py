#!/usr/bin/env python3
"""부곡CC 홀별 코스공략 야디지북 PDF 생성.

    python build.py                                  # data/bugok_cc.json -> out/부곡CC_야디지북.pdf
    python build.py --tee champion                   # 기준 티 변경 (champion/regular/lady)
    python build.py --data data/sample_filled.json   # 채워진 예시 데이터로 미리보기
"""

from __future__ import annotations

import argparse
import os
import sys

from yardagebook import book, course as course_mod, fonts

DEFAULT_DATA = os.path.join("data", "bugok_cc.json")
DEFAULT_OUT = os.path.join("out", "부곡CC_야디지북.pdf")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="부곡CC 야디지북 PDF 생성기")
    ap.add_argument("--data", default=DEFAULT_DATA, help=f"코스 데이터 JSON (기본: {DEFAULT_DATA})")
    ap.add_argument("--out", default=None, help=f"출력 PDF 경로 (기본: {DEFAULT_OUT})")
    ap.add_argument("--tee", default="regular", help="플랜/도면 기준 티 (기본: regular)")
    ap.add_argument(
        "--holes",
        default=None,
        help="일부 홀만 생성 (예: 1, 1-3, 1,5,9). 생략하면 전체 18홀",
    )
    args = ap.parse_args(argv)

    if not os.path.exists(args.data):
        print(f"[오류] 데이터 파일이 없습니다: {args.data}", file=sys.stderr)
        return 1

    font_desc = fonts.register()

    try:
        crs = course_mod.load(args.data)
    except (ValueError, KeyError) as exc:
        print(f"[오류] 데이터 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1

    tee_keys = [t["key"] for t in crs.tees]
    if args.tee not in tee_keys:
        print(f"[오류] --tee 는 {tee_keys} 중 하나여야 합니다.", file=sys.stderr)
        return 1

    if args.holes:
        try:
            wanted = parse_holes(args.holes)
        except ValueError as exc:
            print(f"[오류] --holes 값을 이해할 수 없습니다: {exc}", file=sys.stderr)
            return 1
        selected = [h for h in crs.holes if h.hole in wanted]
        if not selected:
            print(f"[오류] --holes {args.holes} 에 해당하는 홀이 없습니다.", file=sys.stderr)
            return 1
        crs.holes = selected

    out_path = args.out or DEFAULT_OUT
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    book.build(crs, out_path, args.tee)

    filled = sum(1 for h in crs.holes if h.known and h.par)
    with_map = sum(1 for h in crs.holes if h.image)
    print(f"생성 완료: {out_path}")
    print(f"  폰트      : {font_desc}")
    print(f"  기준 티   : {args.tee}")
    print(f"  홀        : {', '.join(str(h.hole) for h in crs.holes)}")
    print(f"  데이터    : {filled}/{len(crs.holes)}홀 입력됨, 코스안내도 {with_map}장")
    if filled < len(crs.holes):
        print(f"  → {args.data} 의 par / handicap / tees 를 채우면 빈칸이 실제 값으로 바뀝니다.")
    return 0


def parse_holes(spec: str) -> set[int]:
    """'1', '1-3', '1,5,9' 형태를 홀 번호 집합으로."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    if not out:
        raise ValueError(spec)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
