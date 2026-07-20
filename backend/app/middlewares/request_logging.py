from __future__ import annotations

import logging
import time
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.security import decode_access_token

logger = logging.getLogger("pigo.request")


def _safe_user_from_request(request: Request) -> dict[str, str | None]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"sub": None, "email": None, "cnpj": None}

    try:
        payload = decode_access_token(auth_header.replace("Bearer ", "").strip())
    except Exception:
        return {"sub": "invalid-token", "email": None, "cnpj": None}

    return {
        "sub": str(payload.get("sub") or "") or None,
        "email": str(payload.get("email") or "") or None,
        "cnpj": str(payload.get("cnpj") or "") or None,
    }


async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
    started_at = time.perf_counter()
    user = _safe_user_from_request(request)
    params = dict(request.query_params)

    logger.info(
        "request.start trace_id=%s method=%s endpoint=%s user=%s empresa_id=%s params=%s",
        trace_id,
        request.method,
        request.url.path,
        user,
        params.get("empresa_id"),
        params,
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        stack = traceback.format_exc()
        logger.error(
            "request.error trace_id=%s method=%s endpoint=%s user=%s empresa_id=%s params=%s duration_ms=%s error=%s\n%s",
            trace_id,
            request.method,
            request.url.path,
            user,
            params.get("empresa_id"),
            params,
            duration_ms,
            repr(exc),
            stack,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "endpoint": request.url.path,
                "error": "Erro interno ao processar a requisicao.",
                "details": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "traceId": trace_id,
            },
            headers={"X-Trace-Id": trace_id},
        )

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Trace-Id"] = trace_id
    logger.info(
        "request.end trace_id=%s method=%s endpoint=%s status=%s duration_ms=%s",
        trace_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
