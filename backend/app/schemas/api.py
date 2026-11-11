"""Request and response schemas for the public REST API (/api/v1)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import QuestionType


class Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- common
class HealthOut(Out):
    status: Literal["ok"]
    version: str
    environment: str
    ai_provider: str


class ErrorBody(Out):
    code: str
    message: str
    details: Any | None = None


class ErrorOut(Out):
    error: ErrorBody


# ---------------------------------------------------------------- profile
class ProfileOut(Out):
    id: str
    email: str | None
    display_name: str
    created_at: datetime | None


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


# ---------------------------------------------------------------- workspaces
class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceOut(Out):
    id: str
    name: str
    description: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- documents
DocStatus = Literal["UPLOADED", "PROCESSING", "READY", "FAILED"]


class DocumentOut(Out):
    id: str
    workspace_id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: DocStatus
    page_count: int | None = None
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime


class SummaryRequest(BaseModel):
    force: bool = False


class SummaryOut(Out):
    document_id: str
    summary: dict[str, Any]
    model_name: str | None
    created_at: datetime
    cached: bool


# ---------------------------------------------------------------- chat
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_ids: list[str] | None = Field(default=None, max_length=20)


class CitationOut(Out):
    label: str
    chunk_id: str
    document_id: str | None
    filename: str
    page_number: int | None
    section_title: str | None
    quote_text: str
    score: float | None


class MessageOut(Out):
    id: str
    role: Literal["user", "assistant"]
    content: str
    insufficient_evidence: bool = False
    model_name: str | None = None
    created_at: datetime
    citations: list[CitationOut] = []


class ChatResponse(Out):
    conversation_id: str
    user_message: MessageOut
    message: MessageOut
    insufficient_evidence: bool


class ConversationSummaryOut(Out):
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationOut(ConversationSummaryOut):
    messages: list[MessageOut]


# ---------------------------------------------------------------- quiz
class QuizGenerateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    num_questions: int = Field(default=5, ge=1, le=50)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "medium"
    types: list[QuestionType] = Field(default_factory=lambda: ["multiple_choice", "true_false"], min_length=1)
    document_ids: list[str] | None = Field(default=None, max_length=20)


class QuizQuestionPublic(Out):
    id: str
    position: int
    type: QuestionType
    question: str
    options: list[str]
    difficulty: str


class QuizOut(Out):
    id: str
    workspace_id: str
    title: str
    settings_json: dict[str, Any]
    created_at: datetime
    questions: list[QuizQuestionPublic]


class QuizListItem(Out):
    id: str
    title: str
    created_at: datetime
    question_count: int
    attempt_count: int
    best_score: float | None


class AttemptCreate(BaseModel):
    quiz_set_id: str


class AttemptOut(Out):
    id: str
    quiz_set_id: str
    score: float | None
    started_at: datetime
    submitted_at: datetime | None


class AttemptSubmit(BaseModel):
    answers: dict[str, str] = Field(description="question_id -> answer text (option text, 'True'/'False', or free text)")


class SourceRef(Out):
    chunk_id: str
    filename: str | None
    page_number: int | None
    section_title: str | None = None
    quote_text: str


class ResultItem(Out):
    question_id: str
    position: int
    type: QuestionType
    question: str
    options: list[str]
    difficulty: str
    your_answer: str
    is_correct: bool
    feedback: str
    correct_answer: str
    explanation: str
    sources: list[SourceRef]


class AttemptResultOut(Out):
    attempt: AttemptOut
    quiz: dict[str, Any]
    items: list[ResultItem]


# ---------------------------------------------------------------- flashcards
class FlashcardGenerateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    count: int = Field(default=10, ge=1, le=100)
    document_ids: list[str] | None = Field(default=None, max_length=20)


class FlashcardUpdate(BaseModel):
    mastery_status: Literal["NEW", "LEARNING", "MASTERED"]


class FlashcardOut(Out):
    id: str
    set_id: str
    workspace_id: str
    position: int
    front: str
    back: str
    mastery_status: Literal["NEW", "LEARNING", "MASTERED"]
    reviewed_at: datetime | None
    source: SourceRef | None


class FlashcardSetListItem(Out):
    id: str
    title: str
    created_at: datetime
    card_count: int
    mastered_count: int


class FlashcardSetOut(Out):
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    cards: list[FlashcardOut]


class ReviewOut(Out):
    id: str
    flashcard_id: str
    previous_status: str
    new_status: str
    reviewed_at: datetime


# ---------------------------------------------------------------- dashboard / usage
class ActivityOut(Out):
    id: str
    workspace_id: str | None
    activity_type: str
    description: str
    created_at: datetime


class DashboardOut(Out):
    total_workspaces: int
    total_documents: int
    total_study_sessions: int
    total_quizzes: int
    average_quiz_score: float | None
    flashcards_to_review: int
    recent_activity: list[ActivityOut]
    activity_by_day: list[dict[str, Any]]
    quiz_scores: list[dict[str, Any]]
    flashcard_mastery: dict[str, int]


class UsageOut(Out):
    requests_today: int
    daily_limit: int
    tokens_today: int
    estimated_cost_30d: float
    by_operation: list[dict[str, Any]]
    by_day: list[dict[str, Any]]
    provider: str
