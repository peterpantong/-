#!/usr/bin/env python3
"""Claude Code PreToolUse 훅 — 엑셀이 열려 있을 때 쓰기 작업을 차단한다.

엑셀은 파일을 열면 같은 폴더에 `~$파일명.xlsx` 잠금 파일을 만든다.
그 상태에서 openpyxl 등이 저장하면 엑셀의 메모리 사본과 디스크 내용이
어긋나고, 다음 저장에서 한쪽 작업이 통째로 사라진다.

이 훅은 실행하려는 명령이 엑셀과 관련 있고 잠금 파일이 발견되면
도구 호출 자체를 거부한다. Claude의 판단과 무관하게 적용된다.
"""

import json
import os
import re
import sys

# 엑셀을 건드릴 가능성이 있는 명령인지 판단하는 신호
EXCEL_HINTS = re.compile(
    r"openpyxl|xlsxwriter|xlwings|win32com|"
    r"read_excel|to_excel|ExcelWriter|"
    r"\.xlsx|\.xlsm|\.xls\b|\.xltx",
    re.IGNORECASE,
)

# 훑지 않을 폴더 — 여기엔 업무용 엑셀이 없다
SKIP_DIRS = {
    ".git", ".claude", "node_modules", "__pycache__",
    ".venv", "venv", "env", "dist", "build", ".idea", ".vscode",
}

# 작업 폴더 기준 탐색 깊이. 잠금 파일은 원본 바로 옆에 생기므로 깊이 갈 필요가 없다
MAX_DEPTH = 4

LOCK_SUFFIXES = (".xlsx", ".xlsm", ".xls", ".xltx")


def find_locks(root: str) -> list:
    """`~$` 로 시작하는 엑셀 잠금 파일을 모은다."""
    locks = []
    root = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth >= MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for name in filenames:
            if name.startswith("~$") and name.lower().endswith(LOCK_SUFFIXES):
                locks.append(os.path.join(dirpath, name))

    return locks


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # 입력을 못 읽으면 간섭하지 않는다. 훅 때문에 작업이 막히면 안 된다
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""

    if not EXCEL_HINTS.search(command):
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()

    try:
        locks = find_locks(cwd)
    except Exception:
        sys.exit(0)

    if not locks:
        sys.exit(0)

    # `~$` 를 떼서 원본 파일명을 보여준다.
    # 파일명이 길면 엑셀이 앞부분을 잘라 쓰므로 정확하지 않을 수 있다
    opened = sorted({os.path.basename(p)[2:] for p in locks})

    deny(
        "엑셀에서 열려 있는 파일이 있어 쓰기를 차단했습니다: "
        + ", ".join(opened)
        + " — 지금 저장하면 엑셀의 메모리 사본과 충돌해 한쪽 작업이 사라집니다. "
        "사용자에게 해당 파일을 저장 후 닫아달라고 요청하고, "
        "닫힌 것을 확인한 뒤에 다시 실행하세요. 우회하지 마세요."
    )


if __name__ == "__main__":
    main()
