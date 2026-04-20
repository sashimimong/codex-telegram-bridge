# Codex Telegram Bridge

Windows에서 `Codex CLI`를 텔레그램 봇으로 연결해 쓰기 위한 셀프호스트 브리지입니다.

목표는 간단합니다.

- 설치 스크립트 실행
- 로컬 웹 UI에서 토큰과 작업 폴더 설정
- 텔레그램에서 바로 Codex 사용

## 현재 범위

- Windows 우선
- Telegram 전용
- Codex CLI 전용
- 로컬 웹 UI 설정
- 개인 또는 소규모 셀프호스트 사용 기준

## 주요 기능

- 텔레그램 메시지를 Codex CLI에 전달하고 결과를 다시 텔레그램으로 반환
- 허용 사용자 ID 화이트리스트
- 작업 폴더 진단과 경고 표시
- 템플릿 기반 봇 규칙 편집
- 템플릿별 응답 포맷 강제
- 템플릿별 런타임 정책 차등 적용
- 봇 시작 실패 상태를 UI에서 확인 가능
- 저장된 봇 토큰 마스킹 처리
- 한국어 자동 번역 보조 프롬프트는 기본적으로 비활성화

## 빠른 시작

```powershell
git clone https://github.com/sashimimong/codex-telegram-bridge.git
cd codex-telegram-bridge
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8765
```

설정 화면에서 아래 항목을 채우면 됩니다.

1. `Telegram Bot Token`
2. `Allowed User IDs`
3. `Workspace Path`
4. 필요하면 `Codex CLI Path`

## 준비물

- Windows PC
- Python 3.11
- Codex CLI 사용 가능 환경
- 텔레그램 계정
- `@BotFather`로 만든 텔레그램 봇

## 사용 흐름

1. 로컬 웹 UI에서 봇 토큰과 허용 사용자 ID를 저장합니다.
2. Codex가 작업할 프로젝트 폴더를 지정합니다.
3. 오른쪽 진단 패널에서 설치, 로그인, 폴더 상태를 확인합니다.
4. 텔레그램에서 `/start`, `/status` 후 일반 메시지를 보내 테스트합니다.

## 템플릿

기본 제공 템플릿은 출력 구조가 서로 다르게 설계되어 있습니다.

- 기본 개인 비서
- 코딩 보조
- 리서치 정리
- 일상 추천
- 리뷰 모드

각 템플릿은 아래 항목을 빠르게 채워주는 시작점입니다.

- 시스템 규칙
- 응답 스타일
- 응답 포맷
- 작업 방식
- 허용 지침
- 금지 지침

예를 들어 `코딩 보조`는 `문제 요약 / 원인 / 수정 방향 / 검증 방법` 순서로 답하게 만들고, 워크스페이스 맥락을 우선 사용하도록 강제합니다. `리서치 정리`는 `한줄 결론 / 핵심 근거 / 비교 포인트 / 추천` 구조를 따르게 만들고, `리뷰 모드`는 칭찬보다 문제를 먼저 나열하도록 유도합니다.

## 보안 메모

- 저장된 봇 토큰은 UI에서 마스킹되어 보입니다.
- 토큰 입력칸을 비워두고 저장하면 기존 토큰을 유지합니다.
- 허용 사용자 ID를 꼭 설정하세요.
- 작업 폴더는 프로젝트 루트처럼 좁은 범위로 잡는 것을 권장합니다.
- `.bridge_data/` 같은 로컬 설정 파일은 공개 저장소에 올리지 마세요.

## 자주 막히는 지점

### 봇이 응답하지 않을 때

- 텔레그램 토큰이 올바른지 확인
- 허용 사용자 ID에 본인 ID가 들어 있는지 확인
- Codex CLI가 설치되어 있는지 확인
- Codex 로그인 상태 확인
- PC 절전, 네트워크 끊김 여부 확인

### Codex CLI를 못 찾을 때

- `Codex CLI Path`를 비우고 자동 탐지를 먼저 시도
- 필요하면 `codex.cmd` 또는 `codex.exe` 경로를 직접 입력

### 작업 폴더가 애매할 때

- `D:\` 같은 드라이브 루트 대신 실제 프로젝트 폴더를 지정
- 가능하면 `.git`이 있는 저장소 루트를 사용

## 개발

설치:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

테스트:

```powershell
pytest -q
```
