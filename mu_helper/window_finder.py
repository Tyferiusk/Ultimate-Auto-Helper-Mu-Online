"""Detección de ventanas del juego (sin instanciar el hilo principal)."""

from __future__ import annotations

import win32gui

from mu_helper.config import WINDOW_TITLE


def get_game_windows() -> list[tuple[int, int]]:
    handles: list[int] = []

    def enum_callback(hwnd: int, _: object) -> None:
        if win32gui.IsWindowVisible(hwnd) and WINDOW_TITLE in win32gui.GetWindowText(hwnd):
            handles.append(hwnd)

    win32gui.EnumWindows(enum_callback, None)
    handles.sort(key=lambda h: win32gui.GetWindowRect(h)[0])
    return [(hwnd, i + 1) for i, hwnd in enumerate(handles)]
