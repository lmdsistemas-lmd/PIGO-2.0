from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
import threading
import time
import unicodedata
from typing import Any

from sqlalchemy import text

from app.database.connection import SessionLocal


CATALOG_CACHE_TTL_SECONDS = 3600


def normalize_ibge_code(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, float):
        if not value.is_integer():
            return None
        raw = str(int(value))
    else:
        raw = str(value).strip()

    digits = re.sub(r"\D", "", raw)
    if len(digits) != 7:
        return None
    return digits


def normalize_municipality_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.upper().strip().split())


@dataclass(frozen=True)
class MunicipalityResolution:
    latitude: float | None
    longitude: float | None
    resolution_source: str
    confidence: float
    ibge_code: str | None = None
    city: str | None = None
    state: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MunicipalityCoordinateResolver:
    _lock = threading.Lock()
    _loaded_at = 0.0
    _by_code: dict[str, dict[str, Any]] = {}
    _by_name_state: dict[tuple[str, str], list[dict[str, Any]]] = {}
    _overrides: list[dict[str, Any]] = []

    @classmethod
    def clear_cache(cls) -> None:
        with cls._lock:
            cls._loaded_at = 0.0
            cls._by_code = {}
            cls._by_name_state = {}
            cls._overrides = []

    @classmethod
    def _ensure_cache(cls) -> None:
        now = time.monotonic()
        if cls._by_code and now - cls._loaded_at < CATALOG_CACHE_TTL_SECONDS:
            return

        with cls._lock:
            if cls._by_code and now - cls._loaded_at < CATALOG_CACHE_TTL_SECONDS:
                return

            with SessionLocal() as db:
                catalog_rows = db.execute(
                    text(
                        """
                        SELECT ibge_code, name, state_code, latitude, longitude,
                               coordinate_type, source, source_version
                        FROM municipality_geocodes
                        """
                    )
                ).mappings().all()
                override_rows = db.execute(
                    text(
                        """
                        SELECT ibge_code, received_code, city_name, state_code,
                               latitude, longitude, reason
                        FROM municipality_coordinate_overrides
                        WHERE active = true
                        ORDER BY updated_at DESC, created_at DESC
                        """
                    )
                ).mappings().all()

            by_code: dict[str, dict[str, Any]] = {}
            by_name_state: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for raw_row in catalog_rows:
                row = dict(raw_row)
                code = normalize_ibge_code(row["ibge_code"])
                if not code:
                    continue
                by_code[code] = row
                key = (
                    normalize_municipality_name(row["name"]),
                    str(row["state_code"]).upper(),
                )
                by_name_state.setdefault(key, []).append(row)

            cls._by_code = by_code
            cls._by_name_state = by_name_state
            cls._overrides = [dict(row) for row in override_rows]
            cls._loaded_at = now

    def resolve(
        self,
        ibge_code: Any,
        city_name: str | None = None,
        state_code: str | None = None,
    ) -> MunicipalityResolution:
        self._ensure_cache()
        code = normalize_ibge_code(ibge_code)
        state = str(state_code or "").strip().upper() or None
        normalized_name = normalize_municipality_name(city_name)

        if code and code in self._by_code:
            return self._from_catalog(self._by_code[code], "IBGE_CODE", 1.0)

        if normalized_name and state:
            candidates = self._by_name_state.get((normalized_name, state), [])
            if len(candidates) == 1:
                return self._from_catalog(candidates[0], "CITY_STATE", 0.9)

        override = self._find_override(
            raw_code=ibge_code,
            normalized_code=code,
            normalized_name=normalized_name,
            state=state,
        )
        if override:
            return MunicipalityResolution(
                ibge_code=normalize_ibge_code(override.get("ibge_code")) or code,
                city=override.get("city_name") or city_name,
                state=override.get("state_code") or state,
                latitude=float(override["latitude"]),
                longitude=float(override["longitude"]),
                resolution_source="MANUAL_OVERRIDE",
                confidence=1.0,
                warning=override.get("reason"),
            )

        warning = (
            "INVALID_IBGE_CODE"
            if ibge_code not in (None, "") and not code
            else "MUNICIPALITY_NOT_FOUND"
        )
        return MunicipalityResolution(
            ibge_code=code,
            city=city_name,
            state=state,
            latitude=None,
            longitude=None,
            resolution_source="NOT_FOUND",
            confidence=0.0,
            warning=warning,
        )

    def _from_catalog(
        self,
        row: dict[str, Any],
        source: str,
        confidence: float,
    ) -> MunicipalityResolution:
        return MunicipalityResolution(
            ibge_code=str(row["ibge_code"]),
            city=str(row["name"]),
            state=str(row["state_code"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            resolution_source=source,
            confidence=confidence,
        )

    def _find_override(
        self,
        raw_code: Any,
        normalized_code: str | None,
        normalized_name: str,
        state: str | None,
    ) -> dict[str, Any] | None:
        received_code = str(raw_code).strip() if raw_code is not None else None
        for override in self._overrides:
            if normalized_code and override.get("ibge_code") == normalized_code:
                return override
            if received_code and str(override.get("received_code") or "").strip() == received_code:
                return override
            if (
                normalized_name
                and state
                and normalize_municipality_name(override.get("city_name"))
                == normalized_name
                and str(override.get("state_code") or "").upper() == state
            ):
                return override
        return None


class MunicipalityGeocodingService:
    """Boundary for an optional offline/admin geocoding job; never used by Dashboard."""

    @property
    def enabled(self) -> bool:
        return os.getenv("MUNICIPALITY_GEOCODING_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
        }

    def geocode_unresolved(self, *_args, **_kwargs):
        if not self.enabled:
            raise RuntimeError("Geocodificação municipal externa desativada.")
        raise NotImplementedError(
            "Configure um provider backend com rate limit e persistência antes de habilitar."
        )
