import os


REPORT_AI_ENABLED = os.getenv("REPORT_AI_ENABLED", "false").strip().lower() == "true"
REPORT_AI_PROVIDER = os.getenv("REPORT_AI_PROVIDER", "").strip()
REPORT_AI_MODEL = os.getenv("REPORT_AI_MODEL", "").strip()
REPORT_AI_TIMEOUT_SECONDS = int(os.getenv("REPORT_AI_TIMEOUT_SECONDS", "15"))
REPORT_ASSISTANT_RATE_LIMIT_PER_MINUTE = int(os.getenv("REPORT_ASSISTANT_RATE_LIMIT_PER_MINUTE", "30"))
