import hashlib
import time
from collections import defaultdict, deque
from threading import Lock

from app.core.report_ai_config import REPORT_ASSISTANT_RATE_LIMIT_PER_MINUTE
from app.ai.parser.intent_parser import UnsafeReportRequest
from app.ai.providers.deterministic_provider import DeterministicIntentProvider
from app.ai.schemas.intent import ReportAssistantResult
from app.ai.services.intent_to_definition import FILTER_FIELDS, ReportIntentToDefinitionService
from app.ai.validators.permission_validator import ReportPermissionValidator
from app.ai.validators.semantic_validator import ReportSemanticValidator
from app.services.business_knowledge_layer import _normalize
from app.services.report_engine import ReportEngine


_requests = defaultdict(deque)
_rate_lock = Lock()


class ReportAssistantRateLimitError(RuntimeError):
    pass


class ReportAssistantService:
    def __init__(self, provider=None, converter=None, engine=None):
        self.provider = provider or DeterministicIntentProvider()
        self.converter = converter or ReportIntentToDefinitionService()
        self.engine = engine or ReportEngine()
        self.semantic_validator = ReportSemanticValidator()
        self.permission_validator = ReportPermissionValidator()

    def interpret(self, prompt, company_id, tenant_id, user, request_id="", answers=None):
        started = time.perf_counter()
        self._rate_limit(str(user.get("sub") or user.get("id") or "anonymous"))
        try:
            intent, confidence = self.provider.interpret(prompt, answers)
        except UnsafeReportRequest as exc:
            return self._result(False, "REPORT_UNSAFE_REQUEST", request_id, message=str(exc), suggestions=["Descreva somente o resultado de negócio desejado."])
        except ValueError as exc:
            return self._result(False, "REPORT_INTENT_LOW_CONFIDENCE", request_id, message=str(exc), suggestions=self._low_confidence_suggestions())

        unavailable, ambiguities = self.semantic_validator.evaluate(intent)
        if unavailable:
            return self._result(
                False, "REPORT_CONCEPT_UNAVAILABLE", request_id, intent=intent,
                message="Um ou mais conceitos ainda não estão disponíveis para esta empresa.",
                unavailable_concepts=unavailable, suggestions=["receivable"] if "payment" in unavailable else [],
            )

        if ambiguities:
            return self._result(False, "REPORT_INTENT_AMBIGUOUS", request_id, intent=intent, confidence=confidence, questions=self.semantic_validator.questions(ambiguities))
        if confidence < 0.65 or not intent.metrics:
            return self._result(False, "REPORT_INTENT_LOW_CONFIDENCE", request_id, intent=intent, confidence=confidence, message="Não consegui entender o relatório com segurança.", suggestions=self._low_confidence_suggestions())

        self.permission_validator.validate(intent.category, user)
        try:
            self._resolve_filters(intent, tenant_id, company_id)
            definition = self.converter.convert(intent, company_id)
            intent.source = definition.source
        except LookupError as exc:
            return self._result(False, "REPORT_FILTER_NOT_FOUND", request_id, intent=intent, confidence=confidence, message=str(exc), suggestions=["Confira o nome informado ou escolha uma opção no Builder."])
        except ValueError as exc:
            return self._result(False, "REPORT_CONCEPT_UNAVAILABLE", request_id, intent=intent, confidence=confidence, message=str(exc))

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        return self._result(True, "REPORT_INTENT_PARSED", request_id, intent=intent, report_definition=definition, confidence=confidence, warnings=[{"code": "CONFIRMATION_REQUIRED", "message": "Revise a configuração antes de gerar o preview."}, {"code": "PARSE_DURATION", "duration_ms": duration_ms}])

    @staticmethod
    def prompt_hash(prompt):
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _result(success, code, request_id, **kwargs):
        return ReportAssistantResult(success=success, code=code, request_id=request_id, **kwargs)

    def _resolve_filters(self, intent, tenant_id, company_id):
        if not intent.filters:
            return
        category, source = self.converter._select_source(intent)
        for item in intent.filters:
            if not item.requires_resolution:
                continue
            filter_key = FILTER_FIELDS[item.concept]
            options = self.engine.filter_options(category, source, filter_key, tenant_id, company_id, str(item.value))
            normalized = _normalize(str(item.value))
            matches = [option for option in options if _normalize(str(option.get("label", ""))) == normalized]
            if len(matches) != 1:
                raise LookupError(f"Não foi encontrada uma opção única para {item.concept}: {item.value}.")
            item.value = matches[0]["value"]
            item.requires_resolution = False

    @staticmethod
    def _low_confidence_suggestions():
        return ["Informe o que deseja medir.", "Informe como deseja agrupar.", "Informe o período."]

    @staticmethod
    def _rate_limit(key):
        now = time.monotonic()
        with _rate_lock:
            bucket = _requests[key]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= REPORT_ASSISTANT_RATE_LIMIT_PER_MINUTE:
                raise ReportAssistantRateLimitError("Limite de interpretações por minuto excedido.")
            bucket.append(now)
