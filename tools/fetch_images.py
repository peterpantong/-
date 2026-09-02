#!/usr/bin/env python3
"""코스안내도 이미지를 URL 패턴으로 내려받아 images/ 규칙에 맞춰 저장한다.

골프장 사이트는 대개 홀 번호만 바뀌는 규칙적인 이미지 주소를 쓴다. 예를 들어
아난티 남해는 다음과 같다.

    https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-outcourse-hole4.jpg

이 주소의 홀 번호 자리를 {hole} 로 바꿔 넘기면 1~18홀을 한 번에 받는다.

    python tools/fetch_images.py --prefix ananti --holes 1-9 \\
        --template "https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-outcourse-hole{hole}.jpg"

IN 코스가 자체적으로 1~9 번호를 쓰면 --url-hole-offset 로 맞춘다. 아래는 책의
10~18번홀을 URL 의 hole1~hole9 에서 받는 예다.

    python tools/fetch_images.py --prefix ananti --holes 10-18 --url-hole-offset -9 \\
        --template "https://cdn.ananti.kr/plf/ui/img/golfclub/golfclub-incourse-hole{hole}.jpg"

그린 상세도는 --green 을 붙이면 <prefix>_holeNN_green.<ext> 로 저장된다.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 확장자를 URL 이 아니라 실제 내용으로 정한다 (사이트가 엉뚱한 확장자를 쓰는 경우가 있다)
_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
)

USER_AGENT = "Mozilla/5.0 (compatible; yardage-book-fetcher)"


def parse_holes(spec: str) -> list[int]:
    """'1-9' / '1,5,9' / '3' 을 홀 번호 목록으로."""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    if not out:
        raise ValueError(spec)
    return out


def image_ext(data: bytes) -> str | None:
    """내용으로 확장자 판별. 이미지가 아니면 None."""
    for magic, ext in _MAGIC:
        if data.startswith(magic):
            return ext
    return None


def fetch(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="코스안내도 이미지 일괄 내려받기")
    ap.add_argument("--template", required=True,
                    help="홀 번호 자리를 {hole} 로 표시한 URL. 0 채움이 필요하면 {hole:02d}")
    ap.add_argument("--prefix", required=True, help="코스 데이터의 image_prefix (예: ananti)")
    ap.add_argument("--holes", default="1-18", help="받을 홀 번호 (예: 1-9, 1,5,9). 기본 1-18")
    ap.add_argument("--url-hole-offset", type=int, default=0,
                    help="URL 의 홀 번호 = 책의 홀 번호 + 이 값 (IN 코스가 1~9를 쓰면 -9)")
    ap.add_argument("--green", action="store_true", help="그린 상세도로 저장 (_green 접미사)")
    ap.add_argument("--dest", default=os.path.join(_REPO_ROOT, "images"), help="저장 폴더")
    ap.add_argument("--dry-run", action="store_true", help="주소만 출력하고 받지 않음")
    ap.add_argument("--overwrite", action="store_true", help="이미 있는 파일도 다시 받음")
    args = ap.parse_args(argv)

    if "{hole" not in args.template:
        print("[오류] --template 에 {hole} 자리가 없습니다.", file=sys.stderr)
        return 1

    try:
        holes = parse_holes(args.holes)
    except ValueError as exc:
        print(f"[오류] --holes 값을 이해할 수 없습니다: {exc}", file=sys.stderr)
        return 1

    suffix = "_green" if args.green else ""
    os.makedirs(args.dest, exist_ok=True)

    ok = failed = skipped = 0
    for hole in holes:
        url = args.template.format(hole=hole + args.url_hole_offset)
        base = f"{args.prefix}_hole{hole:02d}{suffix}"

        if args.dry_run:
            print(f"  {hole:2d}번홀  {url}")
            continue

        existing = [f for f in os.listdir(args.dest) if os.path.splitext(f)[0] == base]
        if existing and not args.overwrite:
            print(f"  {hole:2d}번홀  건너뜀 (이미 있음: {existing[0]})")
            skipped += 1
            continue

        try:
            data = fetch(url)
        except urllib.error.HTTPError as exc:
            print(f"  {hole:2d}번홀  실패 HTTP {exc.code}  {url}")
            failed += 1
            continue
        except Exception as exc:  # 네트워크 차단·타임아웃 등
            print(f"  {hole:2d}번홀  실패 {type(exc).__name__}: {exc}")
            failed += 1
            continue

        ext = image_ext(data)
        if ext is None:
            # 404 페이지를 200 으로 돌려주는 사이트가 있어 내용으로 다시 확인한다
            print(f"  {hole:2d}번홀  실패 이미지가 아님 ({len(data)}바이트)  {url}")
            failed += 1
            continue

        path = os.path.join(args.dest, base + ext)
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"  {hole:2d}번홀  저장 {os.path.basename(path)}  ({len(data) // 1024}KB)")
        ok += 1

    if args.dry_run:
        print(f"\n{len(holes)}개 주소 (--dry-run)")
        return 0

    print(f"\n성공 {ok} · 건너뜀 {skipped} · 실패 {failed}")
    if ok:
        print(f"{args.dest} 에 저장했습니다. build.py 를 다시 실행하면 반영됩니다.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
