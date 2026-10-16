"""Launch an existing PIGO backend from an explicit local configuration file."""
import argparse
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


PLACEHOLDERS = {"change-this-before-client-deploy", "replace-with-a-generated-secret",
                "change-this-internal-sync-key", "use-the-same-value-as-PIGO_INTEGRATION_TOKEN"}


def configured_environment(root):
    backend = root / "backend"
    if not (backend / "app" / "main.py").is_file():
        raise ValueError("Backend nao encontrado na pasta informada.")
    if not (root / "frontend" / "dist" / "index.html").is_file():
        raise ValueError("Compile o frontend antes de preparar o servico.")
    env_file = backend / ".env"
    if not env_file.is_file():
        raise ValueError("Configure backend/.env localmente; variaveis do terminal do VS Code nao passam automaticamente ao servico.")
    environment = {}
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        environment[name.strip()] = value.strip().strip('"').strip("'")
    required = ["DATABASE_URL", "JWT_SECRET_KEY"]
    for name in required:
        if not environment.get(name) or environment[name] in PLACEHOLDERS:
            raise ValueError(f"Configure {name} em backend/.env sem valores de exemplo.")
    token = environment.get("LICENSE_CONTROL_INTEGRATION_TOKEN") or environment.get("LICENSE_CONTROL_SYNC_KEY")
    if not token or token in PLACEHOLDERS:
        raise ValueError("Configure a integracao oficial do LicenseControl em backend/.env.")
    return backend, environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=4010)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--log-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.log_dir and not args.check:
            args.log_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(args.log_dir / "pigo.log", maxBytes=10 * 1024 * 1024,
                                          backupCount=5, encoding="utf-8")
            logging.basicConfig(level=logging.INFO, handlers=[handler],
                                format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)
        if not 1 <= args.port <= 65535:
            raise ValueError("Porta invalida.")
        backend, environment = configured_environment(args.app_root.resolve())
        os.environ.update(environment)
        os.chdir(backend)
        sys.path.insert(0, str(backend))
        if importlib.util.find_spec("uvicorn") is None:
            raise ValueError("Instale as dependencias do backend no Python escolhido.")
        if args.check:
            print("Configuracao local e layout do PIGO verificados; nenhum banco foi alterado.")
            return 0
        import uvicorn
        from app.main import app
        from frontend_shell import FrontendShell
        application = FrontendShell(app, backend.parent / "frontend" / "dist" / "index.html")
        # Caddy publishes HTTPS. The application itself listens only locally.
        uvicorn.run(application, host="127.0.0.1", port=args.port, workers=1,
                    proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                    **({"log_config": None} if args.log_dir else {}))
        return 0
    except ValueError as exc:
        if args.log_dir and not args.check:
            logging.error("Configuracao invalida: %s", exc)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
