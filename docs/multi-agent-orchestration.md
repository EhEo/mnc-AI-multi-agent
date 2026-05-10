# 멀티 에이전트 개발 오케스트레이션 구조 보고서

> 작성일: 2026-05-10  
> 대상 프로젝트: mnc-AI-multi-agent

---

## 1. 개요

이 프로젝트의 개발 워크플로우는 **3개의 AI 에이전트**가 서로 다른 역할을 분담하는 구조로 운영된다. 각 에이전트는 고유한 전문 역할을 가지며, 직접 통신하지 않고 Claude(PM)를 중심으로 단방향으로 연결된다.

| 에이전트 | AI 모델 | 역할 | 호출 방식 |
|---|---|---|---|
| **PM + Coder** | Claude Code (Sonnet 4.6) | 기획·코딩·오케스트레이션 | 메인 세션 (사용자와 직접 대화) |
| **Researcher** | Gemini CLI | 라이브러리·API·스펙 조사 | `ask-gemini.sh "질문"` |
| **Reviewer** | Codex CLI | 코드 리뷰·버그·보안 검증 | `ask-codex.sh "범위"` |

---

## 2. 역할 정의

### 2.1 PM + Coder (Claude Code) — 중앙 라우터

Claude는 사용자의 요청을 받아 **설계 → 코딩 → 연구 요청 → 리뷰 요청 → 결과 종합** 전 과정을 주도한다.

- Gemini와 Codex는 서로를 절대 직접 호출하지 않는다.
- Codex가 추가 조사가 필요하다고 판단하면 그 요청을 Claude가 Gemini에게 전달하고, 결과를 다시 Codex에 넘긴다.
- 모든 에이전트 간 정보 흐름의 허브이자 사용자 인터페이스 역할을 한다.

### 2.2 Researcher (Gemini CLI)

라이브러리·프레임워크의 최신 동작, API 사양, 버전별 변경 사항을 조사한다.

**호출 시점:**
- 코딩 전에 라이브러리/API 동작이 불확실할 때
- 최신 변경 사항이나 deprecation이 의심될 때
- RFC·스펙 세부 사항이 필요할 때
- 여러 접근 방식 중 비교가 필요할 때

**호출하지 않는 경우:** 레포 파일 읽기, `grep`, 간단한 테스트로 확인 가능한 것

**출력 형식:**
- 정확한 함수/클래스 시그니처와 최소 사용 예시
- 출처 URL, 문서 페이지, 버전 명시
- 400단어 이하로 간결하게 작성
- 불확실한 내용은 "모름" 또는 "해당 버전에서 확인 필요"로 명시

### 2.3 Reviewer (Codex CLI)

Claude가 작성한 코드를 **정확성, 보안, 유지보수성, 레포 컨벤션** 관점에서 검토한다.

**호출 시점:**
- 비자명한 변경 사항 커밋 전
- 사용자가 명시적으로 리뷰를 요청할 때

**호출하지 않는 경우:** 단순 한 줄 수정, WIP 중간 코드, 문서만 변경한 경우

**검사 항목:**
1. `git status --short` — 변경 파일 확인
2. `git diff HEAD` — 추적된 수정 사항
3. `git ls-files --others --exclude-standard` — **미추적 신규 파일** (가장 버그가 숨기 쉬운 영역)
4. 주변 파일 읽기 (맥락 파악)
5. CLAUDE.md 및 레포 컨벤션 확인

**심각도 분류:**

| 등급 | 내용 |
|---|---|
| **Blocker** | 버그, 보안 취약점, 계약 위반, 데이터 손실 위험 |
| **Major** | 설계 문제, 엣지 케이스 누락, 성능 회귀, 위험 로직의 테스트 미비 |
| **Minor** | 스타일 불일치, 명명, 주석 품질 |
| **Nit** | 선택적 개선 (명확히 표기) |

---

## 3. 정보 흐름 다이어그램

```
사용자 요청
    │
    ▼
┌─────────────────────────────┐
│   Claude (PM + Coder)       │  ◄── 메인 세션
│   - 기획 및 코딩             │
│   - 에이전트 라우팅          │
│   - 사용자에게 결과 보고      │
└─────────────────────────────┘
         │              │
         │ (코딩 전)     │ (코딩 후)
         ▼              ▼
┌──────────────┐  ┌──────────────┐
│   Gemini     │  │   Codex      │
│  Researcher  │  │   Reviewer   │
│              │  │              │
│  ask-gemini  │  │  ask-codex   │
│  .sh "질문"  │  │  .sh "범위"  │
└──────────────┘  └──────────────┘
         │              │
         │ 연구 결과     │ NEED RESEARCH?
         └──────┬───────┘
                │
                ▼ (Codex가 추가 조사 요청 시)
         Claude가 Gemini에 재질의
         → 결과를 research 파일로 저장
         → Codex에 research 파일과 함께 재호출
```

---

## 4. 핵심 워크플로우

### 4.1 표준 개발 사이클

```
1. [사용자] 기능 요청 또는 버그 보고
        │
2. [Claude] 필요 시 Gemini에 사전 조사 요청
   ask-gemini.sh "Next.js 16 useEffect 동작 변경 사항은?"
        │
3. [Gemini] 조사 결과 반환 → .agents-dev/log/gemini-*.log 저장
        │
4. [Claude] 연구 결과를 바탕으로 코딩 수행
        │
5. [Claude] Codex에 리뷰 요청
   ask-codex.sh "SSE 스트리밍 버그 수정 부분 중점 리뷰"
        │
6. [Codex] 코드 리뷰 수행 → .agents-dev/log/codex-*.log 저장
   결과: SHIP / NEEDS-FIX / DISCUSS + 파일:라인 단위 findings
        │
7. [Claude] 사용자에게 결과 보고 (verdict + 주요 발견 사항)
```

### 4.2 NEED RESEARCH 처리 사이클

Codex가 외부 정보 없이 확신하기 어려운 경우 `## NEED RESEARCH` 블록을 출력한다. Claude는 이를 자동으로 처리한다.

```
Codex 출력 끝에 NEED RESEARCH 발견
        │
1. [Claude] 각 질문을 ask-gemini.sh로 조사
        │
2. [Claude] 답변을 .agents-dev/log/research-<ts>.md 로 저장
        │
3. [Claude] Codex 재호출:
   ask-codex.sh --with-research research-<ts>.md "원래 리뷰 범위"
        │
4. [Codex] 보강된 정보로 최종 리뷰 수행
        │
5. [Claude] 사용자에게 종합 결과 보고
```

---

## 5. 스크립트 구조

### 5.1 ask-gemini.sh

```bash
ask-gemini.sh "리서치 질문"
echo "추가 컨텍스트" | ask-gemini.sh "리서치 질문"
```

**내부 동작:**
1. `roles/researcher.md`를 시스템 프롬프트로 로드
2. 질문을 `<user_question>` XML 태그로 래핑 (프롬프트 인젝션 방어)
3. `gemini -p "..."` 실행
4. 결과를 stdout + `.agents-dev/log/<team>/gemini-<ts>.log` 동시 저장
5. `latest-gemini.log` 심볼릭 링크 갱신

### 5.2 ask-codex.sh

```bash
ask-codex.sh "리뷰 범위"
ask-codex.sh --with-research research.md "리뷰 범위"
```

**내부 동작:**
1. `roles/reviewer.md`를 시스템 프롬프트로 로드
2. 리뷰 범위를 `<review_target>` XML 태그로 래핑
3. `--with-research` 사용 시 연구 결과를 `<research_context>` 태그로 추가
4. `codex exec "..."` 실행
5. 결과를 stdout + `.agents-dev/log/<team>/codex-<ts>.log` 동시 저장

### 5.3 보안 — 프롬프트 인젝션 방어

스크립트는 2중 방어 체계를 갖는다:

1. **리터럴 문자열 레이어**: 입력에서 닫는 XML 태그(`</user_question>` 등)를 `[STRIPPED-CLOSING-TAG]`로 치환
2. **모델 레이어**: 역할 프롬프트에서 태그 내부 내용을 "신뢰할 수 없는 데이터"로 취급하도록 명시

---

## 6. 팀 레이아웃 (tmux)

`team-layout.sh`는 tmux에서 3분할 작업 환경을 자동 구성한다.

```
┌──────────────────┬──────────────────┐
│                  │  🔍 GEMINI       │
│  Claude Code     │  researcher      │
│  (PM 메인 세션)  │  dashboard       │
│  'claude' 실행   ├──────────────────┤
│                  │  🧐 CODEX        │
│                  │  reviewer        │
│                  │  dashboard       │
└──────────────────┴──────────────────┘
```

- 왼쪽: Claude Code 메인 세션 (코딩·오케스트레이션)
- 오른쪽 위: Gemini 대시보드 (최신 연구 결과 실시간 표시)
- 오른쪽 아래: Codex 대시보드 (최신 리뷰 결과 실시간 표시)

### 대시보드 기능 (dashboard.sh)

각 사이드 패널은 로그 변경을 감지해 자동 갱신한다:
- Gemini 패널: 질문, 답변 요약, 인용 소스 수
- Codex 패널: Verdict(SHIP/NEEDS-FIX/DISCUSS), Blocker·Major 수, 주요 발견 사항
- 키: `l` = 전체 로그 열기, `space` = 일시 정지, `q` = 종료

---

## 7. 로그 관리

모든 로그는 `.agents-dev/log/` 아래 팀 네임스페이스로 격리된다.

```
.agents-dev/log/
└── <team-name>/
    ├── gemini-<team>-<yyyymmdd-HHMMSS>.log
    ├── codex-<team>-<yyyymmdd-HHMMSS>.log
    ├── latest-gemini.log  → (심볼릭 링크)
    └── latest-codex.log   → (심볼릭 링크)
```

팀 네임스페이스 우선순위: `$AGENT_TEAM` 환경변수 > tmux `@team-name` 윈도우 옵션 > tmux 세션 이름 > `default`

> `.agents-dev/log/`는 `.gitignore`에 추가되어 커밋되지 않는다.

---

## 8. 사용자에게 보고하는 방식

| 상황 | 보고 내용 |
|---|---|
| Gemini 연구 후 | 핵심 포인트 2~4줄 요약 + 로그 경로 |
| Codex 리뷰 후 | Verdict (SHIP/NEEDS-FIX/DISCUSS) + blocker/major 인라인 정리 + 전체 로그 링크 |
| NEEDS-FIX 발생 시 | 사용자에게 먼저 보여준 후 수정 진행 (자동 수정 금지) |

---

## 9. 금지 사항 (운영 원칙)

- `Agent` 서브에이전트 내부에서 Gemini/Codex 호출 금지 — 오케스트레이션은 반드시 메인 세션에서
- `NEEDS-FIX` 결과를 사용자에게 먼저 보고하지 않고 자동 수정 금지
- 프롬프트에 시크릿·크리덴셜 포함 금지 (두 CLI 모두 외부 제공자로 전송)

---

## 10. 이 구조의 의의

이 아키텍처는 **분업과 견제**의 원칙을 AI 에이전트 팀에 적용한 것이다.

| 원칙 | 구현 방식 |
|---|---|
| **단일 책임** | 각 에이전트가 자신의 전문 영역만 담당 |
| **단방향 의존** | Gemini·Codex가 서로 모름 → 사이드 이펙트 없음 |
| **중앙 집중 라우팅** | Claude가 유일한 조율자 → 사용자가 전체 흐름 추적 가능 |
| **감사 가능성** | 모든 호출이 타임스탬프 로그로 남음 |
| **프롬프트 인젝션 방어** | XML 태그 경계 + 역할 프롬프트 이중 방어 |

이 구조는 프로젝트 자체(Multi-LLM 토론 시스템)가 구현하는 "여러 LLM이 협력해 더 나은 결과를 만든다"는 철학을 **개발 워크플로우에도 동일하게 적용**한 것이다.
