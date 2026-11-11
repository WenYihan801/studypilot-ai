"""Schemas the LLM must fill. Every model output is validated against these before use."""

from typing import Literal

from pydantic import BaseModel, Field

QuestionType = Literal["multiple_choice", "true_false", "short_answer"]
Difficulty = Literal["easy", "medium", "hard"]


class ChatAnswerDraft(BaseModel):
    answer: str = Field(max_length=12000, description="Markdown answer. Cite sources inline like [S1].")
    cited_sources: list[str] = Field(default_factory=list, description="Labels such as S1, S2 actually used.")
    sufficient_evidence: bool = Field(description="False if the sources do not support an answer.")


class ConceptItem(BaseModel):
    name: str
    explanation: str


class DefinitionItem(BaseModel):
    term: str
    definition: str


class SummaryDraft(BaseModel):
    overview: str
    main_topics: list[str] = Field(default_factory=list)
    key_concepts: list[ConceptItem] = Field(default_factory=list)
    important_definitions: list[DefinitionItem] = Field(default_factory=list)
    important_arguments: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    revision_checklist: list[str] = Field(default_factory=list)


class QuizQuestionDraft(BaseModel):
    type: QuestionType
    question: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(
        default_factory=list, description="4 options for multiple_choice; ['True','False'] for true_false; [] for short_answer."
    )
    correct_answer: str = Field(min_length=1, max_length=1000)
    explanation: str = Field(min_length=1, max_length=2000)
    difficulty: Difficulty
    source_labels: list[str] = Field(default_factory=list)


class QuizDraft(BaseModel):
    questions: list[QuizQuestionDraft]


class ShortAnswerGrade(BaseModel):
    question_id: str
    is_correct: bool
    feedback: str = Field(max_length=1000)


class ShortAnswerGrades(BaseModel):
    grades: list[ShortAnswerGrade]


class FlashcardDraftItem(BaseModel):
    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=1500)
    source_label: str


class FlashcardDraft(BaseModel):
    cards: list[FlashcardDraftItem]
