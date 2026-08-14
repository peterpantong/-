# 데스크탑 ↔ 노트북 연속성 (USB 대신 git)

퇴근 전 데스크탑, 퇴근 후 노트북으로 같은 깨비봇 작업을 이어갈 때.

## 무엇이 따라가고 무엇이 안 따라가나

| 항목 | 저장 위치 | 따라가나 |
|---|---|---|
| 깨비봇 코드 | 프로젝트 폴더 | ○ |
| `CLAUDE.md` | 프로젝트 폴더 | ○ |
| `.claude/settings.json` | 프로젝트 폴더 | ○ |
| 엑셀 분석 파일 | 프로젝트 폴더 | ○ (커밋하면) |
| **Claude Code 대화 이력** | `~/.claude/projects/` | **✗** |

대화 이력은 프로젝트 폴더 밖(사용자 홈)에 PC별로 저장된다. USB로도 git으로도 안 따라간다.
경로가 다르면 `--resume` 목록도 서로 못 본다.

→ 그래서 **다음 세션이 알아야 할 내용은 `CLAUDE.md`와 커밋 메시지에 남긴다.**
   대화에만 있으면 다른 PC에서 사라진 것과 같다.

## 최초 1회 — 데스크탑에서

### 1. 비밀정보부터 분리

코드 안에 증권사 API 키나 계좌번호가 하드코딩돼 있으면 **커밋 전에** 빼낸다.
한 번 커밋되면 나중에 지워도 git 히스토리에 영원히 남는다.

```python
# 이렇게 바꾼다
import os
API_KEY = os.environ["KKAEBI_API_KEY"]
```

키 자체는 각 PC의 `.env`에 두고, `.env`는 커밋하지 않는다 (아래 .gitignore).
`.env`는 USB나 메신저로 옮기지 말고 각 PC에서 따로 입력한다.

### 2. .gitignore 넣고 저장소 만들기

```powershell
cd C:\path\to\깨비봇
copy .gitignore.template .gitignore
git init
git add -A
git status              # ← 비밀정보 파일이 목록에 없는지 눈으로 확인
git commit -m "깨비봇 초기 커밋"
```

GitHub에서 **private** 저장소를 만들고 연결한다.

```powershell
git remote add origin https://github.com/<계정>/kkaebibot.git
git branch -M main
git push -u origin main
```

### 3. 노트북에서

```powershell
git clone https://github.com/<계정>/kkaebibot.git
cd kkaebibot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`.env`는 여기서 새로 만든다 (git으로 안 따라옴).

## 매일 쓰는 흐름

퇴근 전, 데스크탑에서:

```powershell
git add -A
git commit -m "오늘 한 일 한 줄로"
git push
```

집에서, 노트북에서:

```powershell
git pull
claude
```

Claude Code 세션 안에서 "커밋하고 푸시해줘" 라고 시켜도 된다. 커밋 메시지도 알아서 쓴다.

## 주의

- **양쪽에서 동시에 만지지 않는다.** 한쪽에서 push 안 하고 다른 쪽에서 작업하면 충돌난다.
  `git pull` 부터 하는 습관을 들인다.
- **엑셀 파일은 커밋되지만 병합은 안 된다.** 바이너리라서 양쪽에서 같은 xlsx를 고치면
  둘 중 하나를 골라야 한다. 한쪽에서만 편집하는 게 안전하다.
- **USB를 계속 쓸 거면** 최소한 `.env`와 API 키는 빼고 담는다.
