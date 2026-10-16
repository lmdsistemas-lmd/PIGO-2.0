from app.ai.providers.base import ReportIntentProvider


class LLMIntentProvider(ReportIntentProvider):
    """Ponto de extensão futuro; não habilita nem chama modelo externo."""

    def interpret(self, prompt: str, answers: dict[str, str] | None = None):
        raise RuntimeError("LLMIntentProvider não está habilitado nesta versão.")
