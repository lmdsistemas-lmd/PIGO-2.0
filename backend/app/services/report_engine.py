from copy import deepcopy
import hashlib
import json
import logging
import threading
import time

from app.schemas.reporting import ReportDefinition
from app.services.report_provider import FirebirdReportProvider
from app.services.report_query_builder import ReportQueryBuilder

logger = logging.getLogger(__name__)
_cache = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 30


def clear_report_cache(tenant_id: str | None = None):
    with _cache_lock:
        if tenant_id is None:
            _cache.clear()
        else:
            for key in [key for key in _cache if key[0] == str(tenant_id)]:
                _cache.pop(key, None)


class ReportEngine:
    def __init__(self, provider=None, builder=None):
        self.provider = provider or FirebirdReportProvider()
        self.builder = builder or ReportQueryBuilder()

    def execute(self, definition: ReportDefinition, tenant_id: str, empresa_id: int, limit=50, request_id=""):
        started = time.perf_counter()
        fingerprint = hashlib.sha256(
            json.dumps(definition.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        cache_key = (str(tenant_id), str(empresa_id), fingerprint, int(limit))
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and time.monotonic() - cached[0] <= _CACHE_TTL:
                result = deepcopy(cached[1])
                result["cache"] = "hit"
                return result

        sql, params = self.builder.build(definition, empresa_id, limit)
        logger.info("report.engine.start request_id=%s tenant=%s company=%s source=%s", request_id, tenant_id, empresa_id, definition.source)
        rows = [{str(key).lower(): value for key, value in dict(row).items()} for row in self.provider.execute(sql, params)]
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        columns = self._columns(definition, rows)
        result = {
            "success": True,
            "partial": False,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "query_time_ms": duration_ms,
            "chart": definition.chart,
            "cache": "miss",
            "request_id": request_id,
        }
        with _cache_lock:
            _cache[cache_key] = (time.monotonic(), deepcopy(result))
        logger.info("report.engine.end request_id=%s rows=%s duration_ms=%.2f", request_id, len(rows), duration_ms)
        return result

    def _columns(self, definition, rows):
        keys = list(rows[0]) if rows else (
            [f"{item.field}_{item.aggregation}" for item in definition.totals]
            if definition.totals else definition.fields
        )
        source = self.builder.catalog.source(definition.category, definition.source)
        columns = []
        for key in keys:
            base_key = key
            aggregation = ""
            for suffix in ("sum", "avg", "min", "max", "count"):
                if key.endswith(f"_{suffix}"):
                    base_key, aggregation = key[:-(len(suffix) + 1)], suffix
                    break
            label = source["fields"].get(base_key, {}).get("label", key.replace("_", " ").title())
            if aggregation:
                label = f"{label} ({aggregation})"
            semantic = source["fields"].get(base_key, {})
            columns.append({
                "key": key, "label": label, "type": semantic.get("type", "text"),
                "format": semantic.get("format", semantic.get("type", "text")),
                "description": semantic.get("description", ""), "help": semantic.get("help", ""),
                "semantic_id": semantic.get("semantic_id", ""),
            })
        return columns

    def filter_options(self, category, source, filter_key, tenant_id, empresa_id, search=""):
        sql, params = self.builder.build_filter_options(category, source, filter_key, empresa_id, search)
        rows = self.provider.execute(sql, params)
        return [{"value": row.get("VALUE") or row.get("value"), "label": row.get("LABEL") or row.get("label") or row.get("VALUE") or row.get("value")} for row in rows]
