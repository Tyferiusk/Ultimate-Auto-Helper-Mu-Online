"""Hilo de auto poción: alterna Q y W en serie sobre la ventana seleccionada."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor

from mu_helper.config import HEALER_CYCLE_PAUSE_SEC
from mu_helper.win_input import send_qw_potion_cycle


class HealerThread(QThread):
    status_signal = Signal(str, QColor)
    stopped_signal = Signal()

    def __init__(self, get_hwnd: Callable[[], int | None]) -> None:
        super().__init__()
        self._get_hwnd = get_hwnd
        self._running = True

    def run(self) -> None:
        self.status_signal.emit("Auto poción activado (Fin para detener)", QColor(166, 227, 161))
        idle_logged = False
        try:
            while self._running:
                hwnd = self._get_hwnd()
                if hwnd is None:
                    if not idle_logged:
                        self.status_signal.emit(
                            "Auto poción: selecciona una ventana de juego en Control",
                            QColor(243, 139, 168),
                        )
                        idle_logged = True
                    time.sleep(0.4)
                    continue
                idle_logged = False
                send_qw_potion_cycle(hwnd)
                time.sleep(HEALER_CYCLE_PAUSE_SEC)
        finally:
            self.stopped_signal.emit()

    def stop(self) -> None:
        self._running = False
