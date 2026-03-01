# PRD: Threads 팔로잉 계정 게시글 수집 → Obsidian Vault(Google Drive) 저장 서비스 (MVP)

- 문서 버전: v1.0 (Final)
- 작성일: 2026-03-01
- 상태: 확정

## 1) 문제/목표
사용자가 팔로잉 중인 특정 Threads 계정들의 게시글을 수동으로 하루 2회(오전/오후) 수집해, Obsidian에서 바로 읽을 수 있는 마크다운 파일로 Google Drive 지정 폴더에 날짜별 정리 저장한다.

## 2) MVP 범위
### In Scope
- 게시글만 수집 (댓글 제외)
- 수동 실행(CLI 명령)
- 공식 Threads API 우선 연동
- Google Drive API 직접 업로드
- 수집 대상 계정을 CLI 인자로 변경 가능
- 증분 수집: `last_success_at ~ 현재 시각` 구간의 신규 게시글만 반영
- 중복 저장 방지: 기존 파일 존재 시 `skip`
- 날짜 폴더/파일명 날짜는 **게시글 작성일(created_at)의 KST 날짜 기준**

### Out of Scope (MVP 제외)
- 댓글 수집/저장
- 자동 스케줄러(크론/서버리스 트리거)
- 웹 대시보드 UI
- 고급 분석/통계 대시보드

## 3) 대상 사용자
- 본인(운영자 1인)
- CLI 실행 및 OAuth 초기 설정을 수행할 수 있는 사용자

## 4) 사용 시나리오
1. 운영자가 오전에 CLI를 수동 실행한다.
2. 시스템은 마지막 성공 수집 시각 이후~현재 시각 사이의 신규 게시글만 수집한다.
3. Google Drive의 루트 폴더(`1r2pv6RTDIpWt-3iTXvr8OGWUR3rtNgbQ`) 아래, 게시글 작성일(KST) 기준 `YYYY-MM-DD` 폴더에 마크다운 파일을 저장한다.
4. 오후에 다시 수동 실행하면 중복은 skip하고 신규만 저장한다.
5. 다음날 오전 실행 시, 전날 오후 실행 이후 올라온 게시글도 `last_success_at` 기준으로 누락 없이 반영한다.

## 5) 기능 요구사항
### FR-1. CLI 실행
- 예시:
  - `python app/main.py collect --accounts gptaku_ai,unclejobs.ai,aicoffeechat,agenpreneur,qjc.ai,specal1849`
- `--accounts` 파라미터로 대상 계정 목록 변경 가능
- 기본값은 설정 파일(`config/accounts.yaml`)에서 로드

### FR-2. 수집 시간/증분 로직
- 시스템은 마지막 성공 수집 시각(`last_success_at`)을 로컬 상태 저장소에 기록한다.
- 다음 실행 시, 수집 하한은 `last_success_at`, 수집 상한은 현재 실행 시각.
- 첫 실행(상태 파일 없음) 시 수집 하한은 **실행일 KST 00:00:00**으로 설정한다.
- 최종 저장 대상은 위 구간에 생성된 게시글이다.

### FR-3. 중복 제거
- 유니크 키: `(author_id, post_id)`
- 동일 키 파일이 Drive에 존재하면 업로드하지 않고 skip 기록

### FR-4. Google Drive 저장 규칙
- 루트 폴더 ID: `1r2pv6RTDIpWt-3iTXvr8OGWUR3rtNgbQ`
- 하위 폴더: `YYYY-MM-DD` (**created_at KST 기준**)
- 파일명: `YYYY-MM-DD_{author_id}_{post_id}.md` (**YYYY-MM-DD는 created_at KST 기준**)
- 파일 MIME: `text/markdown`

### FR-5. 마크다운 포맷
댓글 섹션은 MVP에서 제외한다.

```markdown
---
source: threads
author_id: {author_id}
post_id: {post_id}
post_url: {post_url}
created_at: {created_at_iso}
collected_at: {collected_at_iso}
---

# {title_from_first_line_80}

## 날짜
{created_at_kst}

## 제목
{title_from_first_line_80}

## 본문 내용
{body_text}
```

- 제목 생성 규칙: 본문 첫 줄을 사용, 80자 이내 truncate
- 본문 비어 있으면 제목은 `Untitled`

### FR-6. 로그/결과 리포트
- 실행 종료 시 요약 출력:
  - 대상 계정 수
  - 조회 게시글 수
  - 신규 저장 수
  - 중복 skip 수
  - 실패 수(계정/API/업로드)
- 로그 파일: `logs/collect-YYYYMMDD-HHMMSS.log`

## 6) 비기능 요구사항
- NFR-1. 재실행 안전성: 동일 시간대 재실행 시 결과 일관성(중복 방지)
- NFR-2. 장애 허용: 일부 계정 실패 시 전체 중단 대신 부분 성공 허용
- NFR-3. 관측성: 오류 원인(인증/권한/레이트리밋/네트워크) 로그 분리
- NFR-4. 보안: API 토큰/시크릿은 `.env`로 관리, 저장소 커밋 금지

## 7) 외부 연동 및 권한
### Threads API (공식)
- OAuth 토큰 발급/갱신 필요
- 권한 스코프 및 엔드포인트는 구현 전 최신 문서 기준 재확인
- 정책: 타인 계정 조회 제한 시 **가능한 범위(내 계정/허용 데이터)만 수집**하고 계속 운영

### Google Drive API
- OAuth Installed App 방식 채택 (운영자 Google 계정 로그인 기반)
- API Key는 업로드 인증에 사용하지 않음
- 루트 폴더 접근 권한(쓰기) 필수

## 8) 데이터 모델 (초안)
- `state/collector_state.json`
```json
{
  "last_success_at": "2026-03-01T08:05:20+09:00",
  "last_run_id": "20260301-080520",
  "version": 1
}
```

- 내부 레코드
  - `author_id`
  - `post_id`
  - `created_at`
  - `text`
  - `post_url`

## 9) 예외/엣지 케이스
- 계정명 오타/비공개/삭제 계정 → 해당 계정만 실패 처리, 나머지 계속 진행
- 동일 본문 다른 post_id → 별도 파일로 저장(정상)
- Drive 폴더 생성 실패 → 실행 실패 처리 + 재시도 가이드 출력
- API rate limit → 지수 백오프(예: 1s, 2s, 4s, 최대 5회)

## 10) 수용 기준 (Acceptance Criteria)
1. CLI에서 `--accounts`로 전달한 계정 목록만 수집한다.
2. 매 실행 시 `last_success_at` 이후~현재 시각 사이의 게시글만 저장된다(날짜 경계 넘어도 누락 없음).
3. 같은 날 오전/오후 2회 실행 시, 두 번째 실행에서 기존 게시글은 skip되고 신규만 저장된다.
4. 파일명은 `YYYY-MM-DD_{author_id}_{post_id}.md` 규칙을 100% 준수한다.
5. 날짜 폴더와 파일명 날짜(`YYYY-MM-DD`)는 게시글 작성일(created_at, KST) 기준이다.
6. 마크다운 파일에 `날짜/제목/본문 내용` 섹션이 포함되고 댓글 섹션은 없다.
7. 수집 완료 후 `last_success_at`이 갱신된다.
8. 일부 계정 실패 시 전체 프로세스는 계속 진행되고, 실패 계정이 로그에 기록된다.
9. Google Drive 지정 루트 하위에 날짜 폴더가 자동 생성된다(없을 때만).

## 11) 구현 단계 제안
### Phase 1 (MVP 핵심)
- 프로젝트 스캐폴딩(Python CLI)
- Threads API 인증/조회 클라이언트
- Drive 업로더 + 날짜 폴더 생성
- Markdown 렌더링 + 파일명 규칙
- 상태 저장(last_success_at) + 중복 skip

### Phase 2 (안정화)
- 재시도/백오프 강화
- 상세 로그/요약 리포트 개선
- 설정 파일 분리(`config.yaml`, `.env.example`)
- 간단 테스트(단위/통합)

## 12) 리스크 및 완화
- R1. Threads API 권한 제한으로 타인 계정 조회 불가 가능성
  - 완화: 구현 시작 전 “권한/엔드포인트 검증 스파이크” 0단계 수행
- R2. Drive OAuth 초기 설정 복잡도
  - 완화: 초기 설정 가이드 문서 + 검증 명령 제공
- R3. 경계 시간(자정 전후) 누락/중복
  - 완화: UTC 저장 + KST 변환 일관화, 경계 테스트 케이스 작성

## 13) 확정된 핵심 결정
1. 수집 대상: 게시글만(댓글 제외)
2. 실행 방식: 수동 실행(CLI)
3. 저장 방식: Google Drive API 직접 업로드
4. 인증 방식: Google OAuth Installed App
5. 중복 정책: 동일 `(author_id, post_id)`는 skip
6. 날짜 기준: 게시글 작성일(created_at, KST)
7. 계정 목록은 CLI 인자로 변경 가능
8. 초기 계정 목록: `gptaku_ai, unclejobs.ai, aicoffeechat, agenpreneur, qjc.ai, specal1849`

