import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+pg8000://postgres@localhost:5432/pigo_dashboard",
)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-before-client-deploy")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))
LICENSE_CENTRAL_URL = os.getenv(
    "LICENSE_CENTRAL_URL",
    "https://lmdsistemasdev.qzz.io",
)
LICENSE_PROJECT_SLUG = os.getenv("LICENSE_PROJECT_SLUG", "p-i-g-o-dashboard")
AGENT_ACTIVATION_LIMIT_PER_HOUR = int(os.getenv("AGENT_ACTIVATION_LIMIT_PER_HOUR", "10"))
LICENSE_CONTROL_SYNC_KEY = os.getenv("LICENSE_CONTROL_SYNC_KEY", "")
LICENSE_CONTROL_INTEGRATION_TOKEN = os.getenv(
    "LICENSE_CONTROL_INTEGRATION_TOKEN",
    LICENSE_CONTROL_SYNC_KEY,
)
BACKEND_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "BACKEND_CORS_ORIGINS",
        (
            "http://localhost:5176,"
            "http://127.0.0.1:5176,"
            "https://pigo.lmdsistemasdev.qzz.io"
        ),
    ).split(",")
    if origin.strip()
]
