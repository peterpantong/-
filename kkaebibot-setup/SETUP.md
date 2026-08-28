# 깨비봇 + Claude Code 로컬 연동 (A 방식)

깨비봇(파이썬, 수동 실행) 폴더에서 Claude Code를 직접 띄워 쓰는 방식.
별도 연동 코드 없이, Claude Code가 깨비봇 스크립트를 그대로 실행하고 코드도 수정한다.

## 1. 설치 (PowerShell)

Node.js가 없으면 먼저 설치한다 (https://nodejs.org, LTS).

```powershell
node --version          # 확인
npm install -g @anthropic-ai/claude-code
claude --version        # 설치 확인
```

Git for Windows도 같이 깔아두는 것을 권장한다. Claude Code 내부 셸 도구가 유닉스 셸을
쓰기 때문에, 없으면 일부 명령이 동작하지 않는다. (https://git-scm.com/download/win)

### 윈도우에서 자주 걸리는 지점

| 증상 | 원인 / 해결 |
|---|---|
| `node: 용어를 인식할 수 없습니다` | Node 미설치. 설치 후 **파워셸 창을 새로 연다** (기존 창은 PATH를 못 읽음) |
| `claude: 용어를 인식할 수 없습니다` | 먼저 새 창에서 재시도. 그래도 안 되면 `npm config get prefix` 로 나온 경로를 시스템 PATH에 추가 |
| `이 시스템에서 스크립트를 실행할 수 없으므로...` | 파워셸 실행 정책. `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| 셸 명령이 이유 없이 실패 | Git for Windows 미설치 |

## 2. 실행

프로젝트 폴더로 이동해서 띄운다. **시작한 폴더가 작업 범위가 된다.**

```powershell
cd C:\path\to\깨비봇
claude
```

폴더명에 **공백이나 한글이 있으면 따옴표로 감싼다.**

```powershell
cd "F:\00. 감사부봇"
```

처음 실행하면 브라우저가 열리면서 로그인 절차가 한 번 진행된다.

> 별도의 "연동" 작업은 없다. 파워셸에서 `claude` 를 실행하는 것 자체가 연동이다.
> 그 시점부터 해당 폴더의 파일을 직접 읽고 고치고, 파이썬 스크립트를 실행한다.

## 3. 첫 실행 시 할 일

세션 안에서 아래를 순서대로 실행한다.

```
/init
```

깨비봇 코드를 읽어서 `CLAUDE.md`를 자동 생성한다. 이 파일에 프로젝트 구조·실행 방법·
관례가 기록되고, 이후 모든 세션에서 자동으로 읽힌다. 직접 손으로 써도 되지만 `/init`이
실제 코드를 보고 쓰기 때문에 정확하다.

생성된 `CLAUDE.md`는 한 번 훑어보고, 틀린 부분이나 빠진 맥락(데이터 출처, API 키 위치,
장중/장마감 실행 시점 등)을 직접 보강한다.

## 4. 권한 설정

기본값은 명령을 실행할 때마다 확인을 묻는다. 파이썬을 자주 돌리면 번거로우므로
이 폴더의 `settings.json`을 깨비봇 폴더의 `.claude\settings.json`으로 복사한다.

```powershell
mkdir C:\path\to\깨비봇\.claude
copy settings.json C:\path\to\깨비봇\.claude\settings.json
```

세션 안에서 `/permissions`로 확인·수정할 수도 있다.

### 주의 — 실주문 스크립트는 허용 목록에 넣지 말 것

깨비봇이 증권사 API로 **실제 주문을 내는 기능**이 있다면, 그 스크립트는 절대
allow 목록에 넣지 않는다. 매번 확인 프롬프트가 뜨는 편이 안전하다.
현재 `settings.json`은 `python` 전체를 허용하고 있으므로, 실주문 코드가 같은
폴더에 있다면 `Bash(python:*)` 항목을 빼고 아래처럼 스크립트 단위로 좁힌다.

```json
"Bash(python screener.py:*)",
"Bash(python fetch_prices.py:*)"
```

## 5. 사용 예

```
장마감 데이터 수집 스크립트 돌리고 결과 요약해줘
스크리닝 로직에서 우선주 제외 조건이 빠진 것 같은데 확인해줘
매직포뮬러 결과를 엑셀 새 시트로 저장하는 함수 추가해줘
어제 커밋 이후로 바뀐 부분 리뷰해줘
```

## 참고 — 나중에 B 방식이 필요해지면

파워셸 스크립트나 작업 스케줄러 흐름 안에서 Claude를 호출하고 싶을 때 쓴다.
수동 실행 단계에서는 필요 없다.

```powershell
$result = claude -p "오늘 스크리닝 결과 요약해줘" --output-format json
```
