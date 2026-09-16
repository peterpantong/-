# 엑셀 잠금 가드 (PreToolUse 훅)

엑셀에서 파일을 열어둔 채 봇이 그 파일을 쓰면 한쪽 작업이 사라진다.
이 훅은 그 상황에서 **도구 호출 자체를 거부**한다. CLAUDE.md와 달리
Claude의 판단과 무관하게 적용되므로, 부탁이 아니라 차단이다.

## 동작

1. Claude가 Bash 명령을 실행하려 할 때마다 훅이 먼저 돈다
2. 명령에 엑셀 관련 신호(`openpyxl`, `.xlsx`, `to_excel` 등)가 없으면 그냥 통과
3. 있으면 작업 폴더에서 `~$*.xlsx` 잠금 파일을 찾는다
4. 잠금이 있으면 거부하고, Claude에게 "사용자에게 엑셀을 닫아달라고 요청하라"고 알린다

`~$` 로 시작하는 숨김 파일은 엑셀이 파일을 열 때 만드는 잠금 표시다.
엑셀을 닫으면 자동으로 사라진다.

## 설치 (Windows)

### 1. 스크립트 배치

`excel_lock_guard.py` 를 아래 위치에 복사한다. 폴더가 없으면 만든다.

```
C:\Users\<사용자명>\.claude\hooks\excel_lock_guard.py
```

탐색기 주소창에 `%USERPROFILE%\.claude` 를 붙여넣으면 해당 폴더로 이동한다.

### 2. settings.json에 등록

`C:\Users\<사용자명>\.claude\settings.json` 을 연다. 파일이 없으면 만든다.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"C:/Users/<사용자명>/.claude/hooks/excel_lock_guard.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

`<사용자명>` 두 군데를 실제 계정명으로 바꾼다.
경로에 **슬래시(`/`)를 쓴다** — JSON에서 역슬래시는 이스케이프가 필요해 실수가 잦다.
파이썬이 `python` 으로 안 잡히면 `py` 로 바꾼다.

**이미 `settings.json` 이 있다면** 통째로 덮어쓰지 말고 `hooks` 키만 추가한다.
`permissions` 같은 기존 설정이 날아간다.

### 3. 세션 재시작

훅은 세션 시작 시점에 읽힌다. 열려 있던 세션은 종료했다가 다시 띄운다.

## 확인

1. 아무 엑셀 파일을 **엑셀로 연다**
2. 같은 폴더에서 Claude Code를 띄우고 시킨다:
   `openpyxl로 이 폴더 xlsx 파일 시트 이름 확인해줘`
3. 거부되면서 파일을 닫아달라는 안내가 나오면 정상이다
4. 엑셀을 닫고 다시 시키면 통과한다

## 범위와 한계

**작업 폴더 아래 4단계까지** 훑는다. 잠금 파일은 원본 바로 옆에 생기므로
이 정도면 충분하고, 더 깊이 가면 매 명령마다 느려진다.

**폴더 안에 열린 엑셀이 하나라도 있으면 엑셀 관련 명령을 전부 막는다.**
다른 파일을 건드리는 작업도 함께 막히지만, 데이터 유실을 막는 쪽이 낫다는 판단이다.
너무 자주 걸리면 `MAX_DEPTH` 를 줄이거나 프로젝트별 훅으로 범위를 좁힌다.

**입력을 못 읽거나 탐색에 실패하면 통과시킨다.** 훅이 고장 나서 작업 전체가
막히는 상황을 피하기 위한 설계다. 그래서 이 훅만 믿지 말고,
스크립트 안에도 잠금 검사를 같이 넣는 것을 권한다.

```python
from pathlib import Path

def 열려있나(xlsx: Path) -> bool:
    return (xlsx.parent / ("~$" + xlsx.name)).exists()

if 열려있나(경로):
    raise SystemExit(f"엑셀에서 {경로.name} 이(가) 열려 있습니다. 닫고 다시 실행하세요.")
```

## 프로젝트별로 적용하려면

전역 대신 특정 폴더에서만 쓰려면 같은 `hooks` 블록을
`프로젝트폴더\.claude\settings.json` 에 넣는다. 스크립트 경로는
`${CLAUDE_PROJECT_DIR}/.claude/hooks/excel_lock_guard.py` 로 쓸 수 있다.
