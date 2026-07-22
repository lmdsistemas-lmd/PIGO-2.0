from app.ai.parser.intent_parser import DeterministicIntentParser
from app.ai.providers.base import ReportIntentProvider
from app.ai.schemas.intent import ReportIntent


class DeterministicIntentProvider(ReportIntentProvider):
    def __init__(self, parser=None):
        self.parser = parser or DeterministicIntentParser()

    def interpret(self, prompt: str, answers: dict[str, str] | None = None) -> tuple[ReportIntent, float]:
        return self.parser.parse(prompt, answers)
