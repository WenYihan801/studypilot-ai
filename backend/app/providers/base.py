"""Provider-agnostic AI interface. Business code depends only on this module."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

EmbedTask = Literal["document", "query"]
ModelRole = Literal["chat", "quiz"]


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TextResult:
    text: str
    usage: Usage


@dataclass
class StructuredResult[T: BaseModel]:
    data: T
    usage: Usage


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    usage: Usage = field(default_factory=lambda: Usage(model="unknown"))


class AIProvider(ABC):
    name: str

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: ModelRole = "chat",
        max_output_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> TextResult: ...

    @abstractmethod
    def generate_structured_output(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        role: ModelRole = "chat",
        max_output_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> StructuredResult[T]:
        """Must return an instance already validated by `schema` (Pydantic)."""

    @abstractmethod
    def embed_texts(self, texts: list[str], *, task: EmbedTask) -> EmbedResult:
        """Returns one L2-normalised vector of length EMBEDDING_DIM per input text."""


def l2_normalize(vec: list[float]) -> list[float]:
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec] if norm else vec
