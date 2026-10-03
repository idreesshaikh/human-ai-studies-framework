"""HTTP request models for the study service.

Keeping the wire models in one place makes the boundary between the API
controller layer and the domain services visible.  These classes describe
transport only; validation and persistence stay in the service modules.
"""

from typing import Literal

from pydantic import BaseModel, Field


class StudyEventIn(BaseModel):
    """One event submitted by TERN or an optional external producer."""

    sessionId: str
    seq: int
    v: int = -1
    ts: str = ""
    mono: float = -1
    participantId: str = ""
    condition: str = ""
    taskId: str = ""
    type: str = ""
    payload: dict = Field(default_factory=dict)
    source: str = ""


class EventBatch(BaseModel):
    """The event ingest envelope; a bare event array is also accepted."""

    source: str = ""
    events: list[StudyEventIn]


class RecipeRunIn(BaseModel):
    """One recipe run recorded by the analysis runner."""

    recipeId: str
    status: str = "ok"
    answers: list[str] = Field(default_factory=list)
    note: str = ""


class PaperIngestIn(BaseModel):
    """One paper identifier submitted to the literature service."""

    arxivId: str = ""
    doi: str = ""


class PaperLinksIn(BaseModel):
    """Replacement links from a paper to protocol elements."""

    targets: list[str] = Field(default_factory=list)


class MatchIn(BaseModel):
    """One idea-to-paper matching request."""

    query: str
    limit: int = 5


class FromMatchIn(BaseModel):
    """Accept one recommendation into a study's paper set."""

    ref: str
    matchReason: str = ""


class FromGraphIn(BaseModel):
    """Add a paper whose metadata is already warm in the study graph."""

    ref: str


class DecisionTriggerIn(BaseModel):
    """The card action that caused an assistant follow-up."""

    moveId: str
    action: Literal["accepted", "rejected", "noted"]


class ConversationTurnIn(BaseModel):
    """One researcher turn in the design conversation."""

    text: str
    author: str = "Researcher"
    steer: str | None = None
    decision: DecisionTriggerIn | None = None
    # A streamed request can be retried through the blocking endpoint.  Reusing
    # this key keeps that retry idempotent.
    requestId: str | None = None


class MoveDecisionIn(BaseModel):
    """Accept, reject, or reopen one design move."""

    status: str
    decidedBy: str = "Researcher"


class CompileIn(BaseModel):
    """Compile accepted moves into a draft diff."""

    baseYaml: str | None = None


class ApproveIn(BaseModel):
    """Apply one compiled diff."""

    compilationId: str
    approvedBy: str = "Researcher"
    rationale: str = ""


class QuickProtocolIn(BaseModel):
    """The bounded no-chat path for a supported developer study."""

    title: str = Field(min_length=3, max_length=160)
    researchQuestion: str = Field(min_length=10, max_length=500)
    design: Literal["within-subjects", "between-subjects"]
    conditions: list[str] = Field(min_length=2, max_length=2)
    participantDescription: str = Field(min_length=2, max_length=240)
    plannedParticipants: int = Field(ge=4, le=1000)
    taskDescription: str = Field(min_length=8, max_length=500)
    sessionMinutes: int = Field(ge=15, le=180)
    measures: list[str] = Field(min_length=1, max_length=6)
    counterbalanced: bool = True


class SessionStartIn(BaseModel):
    """Open a collection session under the current protocol revision."""

    sessionId: str


class TemplateInstantiateIn(BaseModel):
    """Template parameters submitted for protocol instantiation."""

    parameters: dict = Field(default_factory=dict)
    studyId: str = ""
    title: str = ""


class MintTokensIn(BaseModel):
    """Request a batch of participant or session enrollment tokens."""

    count: int = 1
    grain: str = "participant"
    overrides: dict | None = None


class RedeemIn(BaseModel):
    """The token half of a participant connection string."""

    token: str


class ToggleIn(BaseModel):
    """One researcher-approved capture setting change."""

    instrument: str
    path: list[str]
    value: object
    rationale: str = ""


class SimulateIn(BaseModel):
    """Synthetic rehearsal settings."""

    count: int = 5
    profile: str = "mixed"
    seed: int | None = None


__all__ = [
    "ApproveIn",
    "CompileIn",
    "ConversationTurnIn",
    "DecisionTriggerIn",
    "EventBatch",
    "FromGraphIn",
    "FromMatchIn",
    "MatchIn",
    "MintTokensIn",
    "MoveDecisionIn",
    "PaperIngestIn",
    "PaperLinksIn",
    "QuickProtocolIn",
    "RecipeRunIn",
    "RedeemIn",
    "SessionStartIn",
    "SimulateIn",
    "StudyEventIn",
    "TemplateInstantiateIn",
    "ToggleIn",
]
