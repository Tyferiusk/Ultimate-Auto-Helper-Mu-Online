"""
Ultimate Mu Helper — punto de entrada.

- En .exe (PyInstaller): carpeta de trabajo = carpeta del ejecutable (license.dat, logs, imagenes/).
- Plantillas PNG: preferentemente en subcarpeta `imagenes/` junto al .exe (o en la misma carpeta).
"""

from __future__ import annotations

import os
import sys


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


_ROOT = _app_dir()
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from mu_helper.elevate_admin import ensure_admin

    ensure_admin(_ROOT)

    from mu_helper.config import SINGLE_INSTANCE_MUTEX_NAME
    from mu_helper.logging_utils import init_session_log, write_log
    from mu_helper.single_instance import (
        acquire_single_instance,
        notify_duplicate_instance,
        release_single_instance,
    )

    if not acquire_single_instance(SINGLE_INSTANCE_MUTEX_NAME):
        notify_duplicate_instance(
            "Ultimate Mu Helper",
            "Ya hay una instancia en ejecución.\n\n"
            "Cierra la otra ventana o finaliza el proceso en el administrador de tareas.",
        )
        return 1

    init_session_log()

    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
        import pyautogui  # noqa: F401
        import win32gui  # noqa: F401
        import win32api  # noqa: F401
        import win32con  # noqa: F401
        import win32crypt  # noqa: F401  # DPAPI (licencia); viene con pywin32
        import ntplib  # noqa: F401
        import wmi  # noqa: F401
        import requests  # noqa: F401
        from PySide6.QtWidgets import QApplication  # noqa: F401
        import mss  # noqa: F401
        from pynput import keyboard  # noqa: F401
    except ImportError as e:
        try:
            from tkinter import messagebox

            messagebox.showerror("Dependencias", f"Falta instalar o importar: {e}")
        except Exception:
            print("Falta instalar dependencias:", e, file=sys.stderr)
        return 1

    import pyautogui

    pyautogui.FAILSAFE = False

    from PySide6.QtWidgets import QApplication

    from mu_helper.templates import load_item_templates
    from mu_helper.ui_main import MainWindow
    from mu_helper.ui_styles import apply_app_style

    try:
        item_templates = load_item_templates()
    except Exception as e:
        write_log(f"Error cargando plantillas: {e}", "ERROR")
        return 1

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(release_single_instance)
    apply_app_style(app)
    window = MainWindow(item_templates)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
