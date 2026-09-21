"""Registro en archivo y utilidades de error."""

from __future__ import annotations

import traceback
from datetime import datetime

from mu_helper.config import LOG_FILE


def write_log(message: str, level: str = "INFO") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except OSError:
        pass
    except Exception:
        pass


def log_error(error: BaseException) -> None:
    write_log(f"ERROR: {error}", "ERROR")
    write_log(traceback.format_exc(), "TRACE")


def init_session_log() -> None:
    write_log("=" * 60)
    write_log("ULTIMATE MU HELPER - INICIO")
    write_log("=" * 60)
