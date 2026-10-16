from abc import ABC, abstractmethod

from app.ai.schemas.intent import ReportIntent


class ReportIntentProvider(ABC):
    """Contrato estável para qualquer mecanismo de interpretação."""

    @abstractmethod
    def interpret(self, prompt: str, answers: dict[str, str] | None = None) -> tuple[ReportIntent, float]:
        raise NotImplementedError
