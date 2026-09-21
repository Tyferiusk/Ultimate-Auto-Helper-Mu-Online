"""Relanzar el proceso con privilegios de administrador (Windows)."""

from __future__ import annotations

import ctypes
import os
import sys


def is_user_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(working_dir: str) -> None:
    """Solicita UAC y sale; el nuevo proceso continúa con permisos elevados."""
    exe = sys.executable
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ret = int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params if params else None,
            working_dir,
            1,  # SW_SHOWNORMAL
        )
        or 0
    )
    if ret <= 32:
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                "No se pudo elevar a administrador (UAC cancelado o denegado).",
                "Ultimate Mu Helper",
                0x10,
            )
        except Exception:
            pass
        raise SystemExit(1)
    raise SystemExit(0)


def ensure_admin(working_dir: str | None = None) -> None:
    if sys.platform != "win32":
        return
    if os.environ.get("MU_HELPER_SKIP_ADMIN", "").strip():
        return
    if is_user_admin():
        return
    relaunch_as_admin(working_dir or os.getcwd())
