import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_PATH = Path("logs")
LOG_FILE = LOGS_PATH / "app.log"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Shared logging setup for both main.py (cron/RUN_ONCE) and the api/ service, so
    the dashboard's log viewer sees activity from either entry point. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    LOGS_PATH.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    root = logging.getLogger()
    root.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
