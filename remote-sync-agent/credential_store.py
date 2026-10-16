import base64
import ctypes
import hashlib
import json
import os
import platform
import socket
import uuid
import secrets
from ctypes import wintypes
from pathlib import Path

STORE_VERSION = 1
STORE_SCOPE = "LocalMachine"

class CredentialStoreError(RuntimeError):
    pass

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer

def _protect_windows(data: bytes) -> bytes:
    source, source_buffer = _blob(data); result = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 0x4, ctypes.byref(result)):
        raise ctypes.WinError()
    try: return ctypes.string_at(result.pbData, result.cbData)
    finally: ctypes.windll.kernel32.LocalFree(result.pbData)

def _unprotect_windows(data: bytes) -> bytes:
    source, source_buffer = _blob(data); result = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise ctypes.WinError()
    try: return ctypes.string_at(result.pbData, result.cbData)
    finally: ctypes.windll.kernel32.LocalFree(result.pbData)

class CredentialStore:
    def __init__(self, path: Path | None = None, installation_path: Path | None = None):
        if path is None:
            data_dir = Path(os.getenv("PIGO_REMOTE_SYNC_DATA_DIR", Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) / "PIGO Remote Sync"))
            path = data_dir / "credentials.dat"
        self.path = path if isinstance(path, Path) else Path(path)
        selected_installation = installation_path or self.path.parent / "installation.json"
        self.installation_path = selected_installation if isinstance(selected_installation, Path) else Path(selected_installation)
        self.insecure_fallback = os.getenv("PIGO_ALLOW_INSECURE_CREDENTIAL_STORE", "").lower() == "true"

    def _read(self) -> dict:
        if not self.path.exists(): return {"version": STORE_VERSION, "scope": STORE_SCOPE, "entries": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") == STORE_VERSION and isinstance(data.get("entries"), dict): return data
            # Formats used by 0.1.0 and by the legacy agent are migrated in memory.
            entries = {}
            for old, new in (("firebirdPassword", "firebird_password"), ("licenseApiKey", "license_api_key"), ("remote_sync_token", "remote_sync_token")):
                item = data.get(old)
                if isinstance(item, dict) and item.get("value"): entries[new] = item["value"]
            if data.get("token"): entries["remote_sync_token"] = data["token"]
            return {"version": STORE_VERSION, "scope": STORE_SCOPE, "entries": entries}
        except (OSError, ValueError, TypeError) as exc:
            raise CredentialStoreError("Arquivo de credenciais invalido.") from exc

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def _identity(self) -> dict:
        if not self.installation_path.exists():
            try:
                legacy = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
                return {"installation_id": legacy.get("installation_id")} if legacy.get("installation_id") else {}
            except (OSError, ValueError): return {}
        try: return json.loads(self.installation_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc: raise CredentialStoreError("Identidade da instalacao invalida.") from exc

    def installation_id(self) -> str:
        data = self._identity()
        if not data.get("installation_id"):
            data = {"version": 1, "installation_id": str(uuid.uuid4())}
            self.installation_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.installation_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8"); temporary.replace(self.installation_path)
        return data["installation_id"]

    @staticmethod
    def machine_fingerprint() -> str:
        return hashlib.sha256(f"{socket.gethostname()}|{uuid.getnode()}|{platform.system()}".encode()).hexdigest()

    def save_token(self, token: str) -> None: self.save_secret("remote_sync_token", token)

    def save_secret(self, name: str, value: str) -> None:
        if not value: raise CredentialStoreError("Segredo vazio nao pode ser salvo.")
        data = self._read(); entries = data.setdefault("entries", {})
        if os.name == "nt": entries[name] = base64.b64encode(_protect_windows(value.encode())).decode()
        elif self.insecure_fallback:
            data["scope"] = "DevelopmentPlaintext"; entries[name] = base64.b64encode(value.encode()).decode()
        else: raise CredentialStoreError("DPAPI indisponivel; fallback inseguro exige habilitacao explicita.")
        data.update({"version": STORE_VERSION, "scope": data.get("scope") or STORE_SCOPE}); self._write(data)

    def load_token(self) -> str | None: return self.load_secret("remote_sync_token")

    def load_secret(self, name: str) -> str | None:
        data = self._read(); entries = data.get("entries", {})
        aliases = {"firebird_password":"firebirdPassword", "license_api_key":"licenseApiKey"}
        value = entries.get(name) or entries.get(aliases.get(name, ""))
        if not value: return None
        try:
            raw = base64.b64decode(value)
            if data.get("scope") == STORE_SCOPE and os.name == "nt": return _unprotect_windows(raw).decode()
            if data.get("scope") == "DevelopmentPlaintext" and self.insecure_fallback: return raw.decode()
        except (OSError, ValueError, UnicodeError) as exc: raise CredentialStoreError("Credencial nao pertence a esta maquina ou esta corrompida.") from exc
        raise CredentialStoreError("Protecao da credencial nao e suportada nesta maquina.")

    def clear_token(self) -> None:
        data = self._read(); data.get("entries", {}).pop("remote_sync_token", None); self._write(data)

    def has_token(self) -> bool: return bool(self.load_token())

    def ensure_ipc_secret(self) -> str:
        value = self.load_secret("ipc_secret")
        if not value:
            value = secrets.token_urlsafe(32)
            self.save_secret("ipc_secret", value)
        return value
