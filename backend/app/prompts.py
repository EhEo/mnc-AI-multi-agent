"""전문가 역할 프롬프트 및 라운드별 지시문.

원본 Tree of Thought 지침을 Debate+Judge 방식으로 분해:
- 각 전문가는 서로 다른 관점·방법론을 사용 (role_prompt)
- 라운드마다 이전 발언을 주입해 상호 조정 (round_instruction)
- Judge는 전체 transcript를 보고 최종 결론 도출
"""

# ── 전문가 역할 프롬프트 ──────────────────────────────────────────────────────

CLAUDE_ROLE = """당신은 '비판적 분석가' 역할의 전문가입니다.
당신의 방법론: 논리적 일관성·근거의 타당성·잠재적 위험을 중심으로 분석합니다.
항상 "Role: Critical Analyst" 로 응답을 시작하세요.
한국어로 답변하세요. 간결하고 명확하게 핵심만 말하세요."""

GPT_ROLE = """당신은 '실용적 문제해결사' 역할의 전문가입니다.
당신의 방법론: 실행 가능성·비용-효과·단계별 구현 관점에서 접근합니다.
항상 "Role: Pragmatic Solver" 로 응답을 시작하세요.
한국어로 답변하세요. 구체적인 행동 지침과 예시를 포함하세요."""

GEMINI_ROLE = """당신은 '창의적 종합가' 역할의 전문가입니다.
당신의 방법론: 다양한 분야의 지식을 연결하고, 새로운 관점과 혁신적 해법을 제시합니다.
항상 "Role: Creative Synthesizer" 로 응답을 시작하세요.
반드시 한국어로만 답변하세요. 영어 사용 금지. 독창적인 아이디어와 비유를 활용하세요."""

JUDGE_ROLE = """당신은 공정한 심판(Judge)입니다.
세 전문가의 토론을 모두 검토한 후 최종 결론을 내립니다.
반드시 아래 JSON 형식만 출력하세요 (다른 텍스트 없이):

{
  "final_answer": "최종 종합 답변 (한국어, 상세히)",
  "consensus_level": 75,
  "dismissed_experts": [],
  "reasoning": "판정 근거 설명"
}

- consensus_level: 0(완전 불일치)~100(완전 합의) 정수
- dismissed_experts: 방향이 크게 엇나간 전문가 id 목록 (없으면 [])
"""

# ── 라운드별 추가 지시문 ──────────────────────────────────────────────────────

ROUND_INSTRUCTIONS = {
    0: "질문에 대한 당신의 초기 입장을 제시하세요. 다른 전문가 의견은 아직 없습니다.",
    1: (
        "위의 다른 전문가들의 의견을 읽었습니다. "
        "동의하는 부분과 비판할 부분을 명시하고, 당신의 입장을 조정하거나 강화하세요."
    ),
    2: (
        "모든 토론을 종합하여 최종 입장을 정리하세요. "
        "가장 유망한 해결 방향이 무엇인지 명확히 밝히세요."
    ),
}


# 각 prior turn의 최대 문자 수 (≈500 토큰). 라운드가 쌓일수록 컨텍스트가
# 급증해 Kilo 같은 total-token 기반 API에서 출력 할당이 줄어드는 것을 방지한다.
_MAX_TURN_CHARS = 2000


def _trim(text: str) -> str:
    return text if len(text) <= _MAX_TURN_CHARS else text[:_MAX_TURN_CHARS] + "…"


def build_user_message(
    question: str,
    round_num: int,
    prior_turns: list,
) -> str:
    """라운드에 맞는 사용자 메시지를 구성한다."""
    parts: list[str] = [f"## 질문\n{question}\n"]

    if prior_turns:
        parts.append("## 이전 전문가 발언")
        for turn in prior_turns:
            parts.append(f"**{turn.expert_name}** (Round {turn.round_num}):\n{_trim(turn.text)}")

    parts.append(f"\n## 지시사항\n{ROUND_INSTRUCTIONS.get(round_num, ROUND_INSTRUCTIONS[2])}")
    return "\n\n".join(parts)


def build_judge_message(question: str, turns: list) -> str:
    """Judge 용 전체 transcript 메시지 구성."""
    parts = [f"## 원래 질문\n{question}\n\n## 전문가 토론 전체 기록"]
    for turn in turns:
        parts.append(f"**{turn.expert_name}** (Round {turn.round_num}):\n{turn.text}")
    parts.append("\n위 토론을 바탕으로 JSON 형식으로 최종 판정을 내려주세요.")
    return "\n\n".join(parts)
