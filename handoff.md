# HANDOFF

작성일: 2026-03-01
프로젝트: Threads 팔로잉 계정 게시글 수집 → Obsidian(Google Drive) 저장 MVP

## 1) 완료된 문서

- PRD: `.omx/plans/prd-threads-obsidian-drive-mvp.md` (v1.0 Final)
- Test Spec: `.omx/plans/test-spec-threads-obsidian-drive-mvp.md` (v1.0)

## 2) 구현 완료 사항

### 핵심 기능

- Python CLI 수집기 구현
  - `python -m app.main collect`
  - `--accounts`로 계정 목록 오버라이드 가능
- 증분 수집 로직
  - `state/collector_state.json`의 `last_success_at` 기준
  - 첫 실행 시 KST 당일 00:00부터 시작
- 마크다운 저장 포맷 구현
  - 날짜 / 제목 / 본문 내용 섹션
  - 댓글 섹션 제외(MVP)
- Google Drive 업로드 구현(OAuth Installed App)
  - 날짜 폴더(`YYYY-MM-DD`) 자동 생성
  - 파일명 `YYYY-MM-DD_{author_id}_{post_id}.md`
  - 날짜 기준은 `created_at(KST)`
- 중복 처리
  - 동일 `(author_id, post_id)` 파일 존재 시 skip
- 에러/로그
  - 계정별 실패는 전체 중단 없이 계속 진행
  - 로그 파일: `logs/collect-YYYYMMDD-HHMMSS.log`

### 다음 단계 구현(추가 반영)

- Threads 공식 흐름 반영 어댑터 개선
  - profile lookup: `/v1.0/profile_lookup?username=...`
  - user threads: `/v1.0/{threads_user_id}/threads`
  - fields/since/until/limit 지원
  - 권한 제한(401/403/404) 에러 메시지 개선
- 점검용 CLI 추가
  - `python -m app.main check-drive`
  - `python -m app.main check-threads --account <username-or-user-id> --limit 3`

## 3) 주요 파일

- `app/main.py`
- `threads_obsidian/config.py`
- `threads_obsidian/threads_client.py`
- `threads_obsidian/drive_client.py`
- `threads_obsidian/collector.py`
- `threads_obsidian/state_store.py`
- `threads_obsidian/markdown.py`
- `threads_obsidian/time_utils.py`
- `tests/test_markdown_logic.py`
- `tests/test_window_and_filtering.py`
- `tests/test_threads_adapter_logic.py`
- `README.md`
- `.env.example`
- `config/accounts.yaml`
- `requirements.txt`

## 4) 검증 결과

- 단위 테스트:
  - `python3 -m unittest discover -s tests -v`
  - 결과: **11 tests OK**
- 컴파일 점검:
  - `python3 -m compileall app threads_obsidian tests`
  - 결과: 성공
- 디버그 잔재 점검:
  - `grep -RInE 'console\.log|debugger|TODO|HACK' app threads_obsidian tests README.md || true`
  - 결과: 매치 없음

## 5) 현재 블로커 및 변경 사항 (실서비스 실행 전)

### A. [해결 완료] 로컬 Python 패키지 설치 및 Google Drive 연동

- Python venv 환경 세팅 및 패키지 설치 완료.
- Google Drive OAuth `drive` 권한 인증 및 지정 폴더 쓰기 확인 완료. (`check-drive` 통과)

### B. [블로커/피봇 필요] 타인 계정 수집 (Threads Access Token)

- 현재 MVP는 Meta의 **공식 Threads API** 규격을 따르고 있음.
- 공식 API는 **본인 계정에 한해서만** 접근을 허용하며, 타인 계정(`gptaku_ai` 등)의 게시글 무단 열람(Scraping)을 차단함 (401/403 Permission 에러 발생).
- **해결 방안:** 타 계정 자동 수집이 목적이라면, 현재의 공식 API HTTP 어댑터(`threads_client.py`)를 걷어내고, **Selenium/Playwright 기반 웹 스크래핑** 또는 **외부 서드파티 크롤링 API (ex: Apify)** 방식으로 아키텍처를 전면 수정해야 함.

## 6) 본 게임 전환 (추후 진행 사항)

1. **[결정 필요]** 무단 수집(크롤링) 방식으로 전환할 것인지, 본인 백업용으로만 작동하게 할 것인지 결정
2. 타인 계정 수집기(크롤링)로 전환 시:
   - Python `playwright` 패키지 추가 또는 서드파티 스크래퍼(API Proxy) 서치
   - 로그인 우회 또는 쿠키 기반 인증 우회 설계
   - `threads_client.py` 를 웹 스크래핑 모듈로 교체

## 7) Meta/Threads 토큰 관련 메모

- Google Drive OAuth는 `state/google_token.json` 형태로 원활하게 자동 갱신되도록 완료.
- 주의: 서드파티 계정 크롤링으로 넘어갈 시, 잦은 IP 요청으로 인해 차단될 수 있으므로 Rate-Limit 방어 로직이 필요해짐.

## 8) 민감정보 주의

- `.env`, `credentials/*.json`, `state/google_token.json`은 커밋 금지 (`.gitignore`에 추가되어 있음)
