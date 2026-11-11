"""Deterministic offline provider for development and tests (AI_PROVIDER=mock).

- Embeddings: hashed bag-of-words, so retrieval genuinely ranks by word overlap.
- Generation: builds plausible, schema-valid outputs from the <sources> block in the prompt.
Special trigger: a question containing MOCK_HALLUCINATE makes the mock cite a non-existent
source, which lets tests prove that citation validation rejects it.
"""

import hashlib
import re

from pydantic import BaseModel

from app.core.config import Settings
from app.providers.base import (
    AIProvider,
    EmbedResult,
    StructuredResult,
    TextResult,
    Usage,
    l2_normalize,
)
from app.schemas.ai import (
    ChatAnswerDraft,
    FlashcardDraft,
    FlashcardDraftItem,
    QuizDraft,
    QuizQuestionDraft,
    ShortAnswerGrade,
    ShortAnswerGrades,
    SummaryDraft,
)

STOPWORDS = set(
    "a an the and or of to in on for is are was were be been it this that with as by at from what which "
    "how why who when where does do did can could should would explain describe give me about between "
    "difference your you i we our their there here into than then also not no yes".split()
)
SOURCE_RE = re.compile(r"\[(S\d+)\][^\n]*\n(.*?)(?=\n\[S\d+\]|\n</sources>)", re.S)
WORD_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS and len(w) > 1]


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if len(p.strip()) > 20]
    return parts or [text.strip()[:200]]


class MockProvider(AIProvider):
    name = "mock"

    def __init__(self, settings: Settings):
        self._dim = settings.embedding_dim

    def _usage(self, prompt: str, out: str) -> Usage:
        return Usage(model="mock-model", input_tokens=len(prompt) // 4, output_tokens=len(out) // 4)

    def embed_texts(self, texts, *, task):
        vectors = []
        for text in texts:
            vec = [0.0] * self._dim
            for w in tokens(text):
                idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % self._dim
                vec[idx] += 1.0
            if not any(vec):
                vec[0] = 1.0
            vectors.append(l2_normalize(vec))
        return EmbedResult(vectors=vectors, usage=Usage(model="mock-embedding", input_tokens=sum(len(t) for t in texts) // 4))

    def generate_text(self, prompt, *, system=None, role="chat", max_output_tokens=1024, temperature=0.3):
        sources = SOURCE_RE.findall(prompt)
        body = " ".join(_sentences(content)[0] for _, content in sources[:3]) if sources else prompt[-300:]
        text = f"- Key points: {body[:600]}"
        return TextResult(text=text, usage=self._usage(prompt, text))

    def generate_structured_output(self, prompt, schema, *, system=None, role="chat", max_output_tokens=2048, temperature=0.2):
        sources = SOURCE_RE.findall(prompt)
        data: BaseModel
        if schema is ChatAnswerDraft:
            data = self._chat(prompt, sources)
        elif schema is QuizDraft:
            data = self._quiz(prompt, sources)
        elif schema is FlashcardDraft:
            data = self._flashcards(prompt, sources)
        elif schema is SummaryDraft:
            data = self._summary(prompt)
        elif schema is ShortAnswerGrades:
            data = self._grades(prompt)
        else:  # pragma: no cover
            raise NotImplementedError(schema.__name__)
        validated = schema.model_validate(data.model_dump())
        return StructuredResult(data=validated, usage=self._usage(prompt, data.model_dump_json()))

    # ---------------------------------------------------------------- builders
    def _chat(self, prompt, sources):
        if "MOCK_HALLUCINATE" in prompt:
            return ChatAnswerDraft(answer="Fabricated claim [S99].", cited_sources=["S99"], sufficient_evidence=True)
        if not sources:
            return ChatAnswerDraft(
                answer="The provided materials do not cover this.", cited_sources=[], sufficient_evidence=False
            )
        label, content = sources[0]
        answer = f"According to your materials, {_sentences(content)[0]} [{label}]"
        return ChatAnswerDraft(answer=answer, cited_sources=[label], sufficient_evidence=True)

    def _quiz(self, prompt, sources):
        n = int(m.group(1)) if (m := re.search(r"exactly (\d+) questions", prompt)) else 3
        allowed = re.search(r"Allowed types: ([a-z_, ]+)", prompt)
        types_ = [t.strip() for t in allowed.group(1).split(",")] if allowed else ["multiple_choice"]
        difficulty = m.group(1) if (m := re.search(r"Difficulty: (easy|medium|hard)", prompt)) else "medium"
        questions = []
        for i in range(n):
            label, content = sources[i % len(sources)] if sources else ("S1", "No content.")
            fact = _sentences(content)[i % len(_sentences(content))][:200]
            qtype = types_[i % len(types_)]
            if qtype == "multiple_choice":
                q = QuizQuestionDraft(
                    type=qtype,
                    question=f"Which statement is supported by the material? ({i + 1})",
                    options=[fact, "None of the materials mention this.", "It is undefined.", "It is always false."],
                    correct_answer=fact,
                    explanation=f"The material states: {fact}",
                    difficulty=difficulty,
                    source_labels=[label],
                )
            elif qtype == "true_false":
                q = QuizQuestionDraft(
                    type=qtype,
                    question=f"True or false: {fact}",
                    options=["True", "False"],
                    correct_answer="True",
                    explanation="This is stated in the material.",
                    difficulty=difficulty,
                    source_labels=[label],
                )
            else:
                q = QuizQuestionDraft(
                    type=qtype,
                    question=f"In your own words, summarise: {fact[:80]}",
                    options=[],
                    correct_answer=fact,
                    explanation="Reference answer from the material.",
                    difficulty=difficulty,
                    source_labels=[label],
                )
            questions.append(q)
        return QuizDraft(questions=questions)

    def _flashcards(self, prompt, sources):
        n = int(m.group(1)) if (m := re.search(r"exactly (\d+) flashcards", prompt)) else 5
        cards = []
        for i in range(n):
            label, content = sources[i % len(sources)] if sources else ("S1", "No content.")
            sent = _sentences(content)[i % len(_sentences(content))]
            words = tokens(sent)
            front = f"({i + 1}) What does the material say about '{words[0] if words else 'this topic'}'?"
            cards.append(FlashcardDraftItem(front=front, back=sent[:500], source_label=label))
        return FlashcardDraft(cards=cards)

    def _summary(self, prompt):
        lines = [ln.strip("- ").strip() for ln in prompt.splitlines() if ln.strip().startswith("- ")]
        lines = lines or ["The document covers its topic in several sections."]
        return SummaryDraft(
            overview=lines[0][:400],
            main_topics=[ln[:80] for ln in lines[:5]],
            key_concepts=[{"name": ln.split()[0] if ln.split() else "Concept", "explanation": ln[:200]} for ln in lines[:3]],
            important_definitions=[],
            important_arguments=lines[:2],
            key_takeaways=lines[:3],
            revision_checklist=[f"Review: {ln[:60]}" for ln in lines[:3]],
        )

    def _grades(self, prompt):
        grades = []
        for qid, reference, student in re.findall(
            r"question_id: (\S+)\nquestion: .*?\nreference_answer: (.*?)\nstudent_answer: (.*?)\n---", prompt, re.S
        ):
            ref, ans = set(tokens(reference)), set(tokens(student))
            overlap = len(ref & ans) / len(ref) if ref else 0
            ok = overlap >= 0.5
            grades.append(
                ShortAnswerGrade(
                    question_id=qid,
                    is_correct=ok,
                    feedback="Covers the key points." if ok else "Missing key points from the reference answer.",
                )
            )
        return ShortAnswerGrades(grades=grades)
