#!/usr/bin/env python3
"""내려받은 코스안내도 이미지를 images/ 규칙에 맞춰 정리한다.

골프장 사이트에서 저장하면 파일명이 제각각이라(`hole1.jpg`, `NH_01_view.png`,
`1번홀_그린.jpg` ...) 직접 바꾸기 번거롭다. 이 스크립트가 홀 번호와 그린 여부를
파일명에서 뽑아 `images/<prefix>_holeNN.<ext>` 로 복사한다.

    python tools/import_images.py --src ~/Downloads/ananti --prefix ananti --dry-run
    python tools/import_images.py --src ~/Downloads/ananti --prefix ananti
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
GREEN_TOKENS = ("green", "그린", "putting")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 앞에 있을수록 우선. 홀 번호를 명시한 형태를 먼저 본다.
_HOLE_PATTERNS = (
    re.compile(r"hole[\s_-]*(\d{1,2})", re.I),
    re.compile(r"(\d{1,2})[\s_-]*번"),
    re.compile(r"\bh(\d{1,2})\b", re.I),
)


def hole_number(name: str) -> int | None:
    """파일명에서 홀 번호(1~18)를 뽑는다. 못 찾으면 None."""
    stem = os.path.splitext(os.path.basename(name))[0]
    for pat in _HOLE_PATTERNS:
        m = pat.search(stem)
        if m and 1 <= int(m.group(1)) <= 18:
            return int(m.group(1))

    # 마지막 수단: 이름에 있는 1~2자리 숫자 중 1~18 범위가 하나뿐이면 그것으로 본다.
    cands = [int(n) for n in re.findall(r"\d{1,2}", stem) if 1 <= int(n) <= 18]
    uniq = sorted(set(cands))
    return uniq[0] if len(uniq) == 1 else None


def is_green(name: str) -> bool:
    stem = os.path.splitext(os.path.basename(name))[0].lower()
    return any(tok in stem for tok in GREEN_TOKENS)


def plan(src_dir: str, prefix: str) -> tuple[list[tuple[str, str]], list[str]]:
    """(원본, 대상) 목록과 판별 실패 목록을 돌려준다."""
    mapped: list[tuple[str, str]] = []
    skipped: list[str] = []

    for entry in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, entry)
        ext = os.path.splitext(entry)[1].lower()
        if not os.path.isfile(path) or ext not in IMAGE_EXTS:
            continue
        n = hole_number(entry)
        if n is None:
            skipped.append(entry)
            continue
        suffix = "_green" if is_green(entry) else ""
        mapped.append((path, f"{prefix}_hole{n:02d}{suffix}{ext}"))

    return mapped, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="코스안내도 이미지 정리")
    ap.add_argument("--src", required=True, help="내려받은 이미지가 있는 폴더")
    ap.add_argument("--prefix", required=True, help="코스 데이터의 image_prefix (예: ananti)")
    ap.add_argument("--dest", default=os.path.join(_REPO_ROOT, "images"), help="대상 폴더")
    ap.add_argument("--dry-run", action="store_true", help="복사하지 않고 결과만 표시")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.src):
        print(f"[오류] 폴더가 없습니다: {args.src}", file=sys.stderr)
        return 1

    mapped, skipped = plan(args.src, args.prefix)
    if not mapped and not skipped:
        print(f"[알림] {args.src} 안에 이미지가 없습니다.")
        return 1

    # 같은 대상에 두 파일이 배정되면 조용히 덮어쓰지 않고 알린다.
    seen: dict[str, str] = {}
    clashes: list[tuple[str, str, str]] = []
    for src, dst in mapped:
        if dst in seen:
            clashes.append((dst, seen[dst], src))
        seen[dst] = src

    for src, dst in mapped:
        print(f"  {os.path.basename(src):40s} -> {dst}")
    for name in skipped:
        print(f"  {name:40s} -> ? 홀 번호를 못 찾음 (직접 이름 변경 필요)")
    for dst, a, b in clashes:
        print(f"[경고] {dst} 에 두 파일이 겹칩니다: {os.path.basename(a)} / {os.path.basename(b)}")

    print(f"\n{len(mapped)}장 인식, {len(skipped)}장 판별 실패")
    if args.dry_run:
        print("--dry-run 이라 복사하지 않았습니다.")
        return 0
    if clashes:
        print("[중단] 겹치는 파일을 정리한 뒤 다시 실행하세요.", file=sys.stderr)
        return 1

    os.makedirs(args.dest, exist_ok=True)
    for src, dst in mapped:
        shutil.copy2(src, os.path.join(args.dest, dst))
    print(f"{args.dest} 에 복사 완료. 이제 build.py 를 다시 실행하면 반영됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
