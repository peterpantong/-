#!/usr/bin/env python3
"""부곡CC 홀별 코스공략 야디지북 PDF 생성.

    python build.py                                  # data/bugok_cc.json -> out/부곡CC_야디지북.pdf
    python build.py --tee blue                       # 기준 티 변경
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
    ap.add_argument("--tee", default="white", help="플랜/도면 기준 티 (기본: white)")
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

    out_path = args.out or DEFAULT_OUT
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    book.build(crs, out_path, args.tee)

    filled = sum(1 for h in crs.holes if h.known and h.par)
    print(f"생성 완료: {out_path}")
    print(f"  폰트      : {font_desc}")
    print(f"  기준 티   : {args.tee}")
    print(f"  데이터    : {filled}/{len(crs.holes)}홀 입력됨")
    if filled < len(crs.holes):
        print(f"  → {args.data} 의 par / handicap / tees 를 채우면 빈칸이 실제 값으로 바뀝니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
