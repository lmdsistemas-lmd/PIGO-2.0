import json
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ResolvedAgentConfig:
    mode: str
    source: Path
    api_base_url: str | None
    company_cnpj: str | None
    remote_sync_token: str | None
    license_api_key: str | None
    firebird_host: str
    firebird_port: int
    firebird_database: str | None
    firebird_user: str | None
    firebird_password: str | None
    firebird_client_path: str | None
    firebird_charset: str
    firebird_driver: str
    runtime_architecture: str | None
    sync_interval_minutes: int
    writeback_enabled: bool = False
    writeback_procedure: str = ""
    writeback_resources: tuple = ()
    operations_map_file: str | None = None

    @classmethod
    def resolve(cls, config_file: Path, env_file: Path, credential_store):
        desktop = config_file.exists()
        document = {}
        if desktop:
            try: document = json.loads(config_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc: raise RuntimeError("Configuracao desktop invalida.") from exc
        firebird = document.get("firebird", {})
        pigo = document.get("pigo", {})
        writeback = document.get("writeback", {}) if desktop else {}
        def secret(primary, *legacy):
            value = credential_store.load_secret(primary)
            for alias in legacy:
                if value: break
                value = credential_store.load_secret(alias)
            return value
        if desktop:
            password = secret("firebird_password", "firebirdPassword")
            license_key = secret("license_api_key", "licenseApiKey")
            remote_token = secret("remote_sync_token")
        else:
            password = os.getenv("FB_PASS") or secret("firebird_password", "firebirdPassword")
            license_key = os.getenv("LICENSE_API_KEY") or secret("license_api_key", "licenseApiKey")
            remote_token = os.getenv("API_TOKEN") or secret("remote_sync_token")
        return cls(
            mode="desktop" if desktop else "legacy", source=config_file if desktop else env_file,
            api_base_url=pigo.get("apiBaseUrl") if desktop else os.getenv("API_BASE_URL"),
            company_cnpj=pigo.get("companyCnpj") if desktop else os.getenv("COMPANY_CNPJ"),
            remote_sync_token=remote_token, license_api_key=license_key,
            firebird_host=str(firebird.get("host") or (None if desktop else os.getenv("FB_HOST")) or "127.0.0.1"),
            firebird_port=int(firebird.get("port") or (None if desktop else os.getenv("FB_PORT")) or 3050),
            firebird_database=firebird.get("database") if desktop else os.getenv("FB_DATABASE"),
            firebird_user=firebird.get("user") if desktop else os.getenv("FB_USER"),
            firebird_password=password,
            firebird_client_path=firebird.get("clientPath") if desktop else os.getenv("FB_CLIENT_PATH"),
            firebird_charset=str(firebird.get("charset") or (None if desktop else os.getenv("FB_CHARSET")) or "WIN1252"),
            firebird_driver=str(firebird.get("driver") or (None if desktop else os.getenv("FB_DRIVER")) or "fdb"),
            runtime_architecture=firebird.get("architecture") if desktop else os.getenv("PIGO_RUNTIME_ARCHITECTURE"),
            sync_interval_minutes=int(pigo.get("syncIntervalMinutes") or (None if desktop else os.getenv("SYNC_INTERVAL_MINUTES")) or 5),
            writeback_enabled=writeback.get("enabled") is True if desktop else os.getenv("WRITEBACK_ENABLED", "false").lower() == "true",
            writeback_procedure=str(writeback.get("procedure", "") if desktop else os.getenv("WRITEBACK_PROCEDURE", "")).strip().upper(),
            writeback_resources=tuple(writeback.get("resources", [])) if desktop else tuple(value.strip() for value in os.getenv("WRITEBACK_RESOURCES", "").split(",") if value.strip()),
            operations_map_file=document.get("operationsMapFile") if desktop else os.getenv("OPERATIONS_MAP_FILE"),
        )

    def firebird_settings(self):
        return {"host":self.firebird_host,"port":self.firebird_port,"database":self.firebird_database,"user":self.firebird_user,"password":self.firebird_password,"charset":self.firebird_charset,"client_path":self.firebird_client_path}

    def validate_firebird(self):
        required={"database":self.firebird_database,"user":self.firebird_user,"password":self.firebird_password}
        missing=[name for name,value in required.items() if not value]
        if missing: raise RuntimeError(f"Configuracao Firebird obrigatoria ausente: {', '.join(missing)}")
