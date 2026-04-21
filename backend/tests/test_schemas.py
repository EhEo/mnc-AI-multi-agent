import json

from app.schemas import (
    DebateStartEvent,
    ExpertMeta,
    ExpertTokenEvent,
    JudgeVerdictEvent,
    RoundStage,
    RoundStartEvent,
    UsageSummary,
)


def test_debate_start_serializes():
    evt = DebateStartEvent(
        question="테스트 질문",
        experts=[
            ExpertMeta(id="claude", name="Claude", model="claude-sonnet-4-6", provider="anthropic")
        ],
        max_rounds=3,
    )
    data = json.loads(evt.model_dump_json())
    assert data["type"] == "debate_start"
    assert data["question"] == "테스트 질문"
    assert len(data["experts"]) == 1


def test_round_start_stage_enum():
    evt = RoundStartEvent(round=0, stage=RoundStage.OPENING)
    data = json.loads(evt.model_dump_json())
    assert data["stage"] == "opening"


def test_expert_token_event():
    evt = ExpertTokenEvent(round=1, expert_id="gpt", delta="안녕")
    data = json.loads(evt.model_dump_json())
    assert data["type"] == "expert_token"
    assert data["delta"] == "안녕"


def test_judge_verdict_event():
    evt = JudgeVerdictEvent(
        final_answer="결론입니다",
        consensus_level=80,
        dismissed_experts=[],
        reasoning="합리적입니다",
        usage=UsageSummary(total_tokens=1000, duration_ms=3000),
    )
    data = json.loads(evt.model_dump_json())
    assert data["type"] == "judge_verdict"
    assert data["consensus_level"] == 80
