from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

# ── Request ──────────────────────────────────────────────────────────────────

class DebateRequest(BaseModel):
    question: str


# ── Transcript ───────────────────────────────────────────────────────────────

@dataclass
class Turn:
    expert_id: str      # "claude" | "gpt" | "gemini" | "judge"
    expert_name: str
    round_num: int
    text: str
    tokens: int = 0


@dataclass
class Transcript:
    turns: list[Turn] = field(default_factory=list)

    def add(self, turn: Turn) -> None:
        self.turns.append(turn)

    def for_round(self, round_num: int) -> list[Turn]:
        return [t for t in self.turns if t.round_num == round_num]

    def before_round(self, round_num: int) -> list[Turn]:
        return [t for t in self.turns if t.round_num < round_num]

    def total_tokens(self) -> int:
        return sum(t.tokens for t in self.turns)


# ── SSE Events (백엔드→프런트 계약) ─────────────────────────────────────────

class RoundStage(StrEnum):
    OPENING = "opening"
    CRITIQUE = "critique"
    FINAL = "final"


class ExpertMeta(BaseModel):
    id: str
    name: str
    model: str
    provider: str


class UsageSummary(BaseModel):
    total_tokens: int
    duration_ms: int


# ── SSE Event payloads ────────────────────────────────────────────────────────

class DebateStartEvent(BaseModel):
    type: Literal["debate_start"] = "debate_start"
    question: str
    experts: list[ExpertMeta]
    max_rounds: int


class RoundStartEvent(BaseModel):
    type: Literal["round_start"] = "round_start"
    round: int
    stage: RoundStage


class ExpertTokenEvent(BaseModel):
    type: Literal["expert_token"] = "expert_token"
    round: int
    expert_id: str
    delta: str


class ExpertDoneEvent(BaseModel):
    type: Literal["expert_done"] = "expert_done"
    round: int
    expert_id: str
    full_text: str
    tokens: int


class JudgeTokenEvent(BaseModel):
    type: Literal["judge_token"] = "judge_token"
    delta: str


class JudgeVerdictEvent(BaseModel):
    type: Literal["judge_verdict"] = "judge_verdict"
    final_answer: str
    consensus_level: int        # 0–100
    dismissed_experts: list[str]
    reasoning: str
    usage: UsageSummary


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class DebateEndEvent(BaseModel):
    type: Literal["debate_end"] = "debate_end"
    total_tokens: int
    duration_ms: int


DebateEvent = (
    DebateStartEvent
    | RoundStartEvent
    | ExpertTokenEvent
    | ExpertDoneEvent
    | JudgeTokenEvent
    | JudgeVerdictEvent
    | ErrorEvent
    | DebateEndEvent
)
