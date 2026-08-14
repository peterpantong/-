"""한글 폰트 등록.

우선순위
  1. fonts/ 디렉터리에 직접 넣어둔 TTF
  2. pip 패키지(koreanize-matplotlib)가 번들한 나눔고딕
  3. 시스템에 설치된 한글 TTF
  4. reportlab 내장 CID 폰트 (파일을 임베딩하지 않으므로 뷰어 한글 폰트팩에 의존)

폰트 이름은 register() 이후에 확정되므로, 다른 모듈에서는 반드시
regular()/bold() 함수로 가져다 쓴다.
"""

from __future__ import annotations

import glob
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

_REGULAR = "Helvetica"
_BOLD = "Helvetica-Bold"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (정규, 볼드) 파일명 후보 — 앞에 있을수록 우선
_TTF_CANDIDATES = [
    ("NanumGothic.ttf", "NanumGothicBold.ttf"),
    ("NanumBarunGothic.ttf", "NanumBarunGothicBold.ttf"),
    ("NotoSansKR-Regular.ttf", "NotoSansKR-Bold.ttf"),
    ("malgun.ttf", "malgunbd.ttf"),
]


def regular() -> str:
    return _REGULAR


def bold() -> str:
    return _BOLD


def _search_dirs() -> list[str]:
    dirs = [os.path.join(_REPO_ROOT, "fonts")]
    try:
        import koreanize_matplotlib  # noqa: F401  (폰트 파일만 빌려 쓴다)

        pkg = os.path.dirname(os.path.abspath(koreanize_matplotlib.__file__))
        dirs.append(os.path.join(pkg, "fonts"))
    except Exception:
        pass
    dirs += [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/Library/Fonts"),
        "/Library/Fonts",
        "C:\\Windows\\Fonts",
    ]
    return [d for d in dirs if os.path.isdir(d)]


def _find(name: str) -> str | None:
    for d in _search_dirs():
        direct = os.path.join(d, name)
        if os.path.isfile(direct):
            return direct
        hits = glob.glob(os.path.join(d, "**", name), recursive=True)
        if hits:
            return hits[0]
    return None


def register() -> str:
    """폰트를 등록하고, 실제로 사용한 폰트 설명을 돌려준다."""
    global _REGULAR, _BOLD

    for regular_file, bold_file in _TTF_CANDIDATES:
        reg_path = _find(regular_file)
        if not reg_path:
            continue
        bold_path = _find(bold_file) or reg_path
        try:
            pdfmetrics.registerFont(TTFont("KRSans", reg_path))
            pdfmetrics.registerFont(TTFont("KRSans-Bold", bold_path))
        except Exception:
            continue
        pdfmetrics.registerFontFamily("KRSans", normal="KRSans", bold="KRSans-Bold")
        _REGULAR, _BOLD = "KRSans", "KRSans-Bold"
        return os.path.basename(reg_path)

    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    _REGULAR = _BOLD = "HYGothic-Medium"
    return "HYGothic-Medium (내장 CID 대체 폰트)"
