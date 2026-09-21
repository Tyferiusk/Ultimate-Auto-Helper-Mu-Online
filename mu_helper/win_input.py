"""Entrada unificada Win32: teclas, ratón y texto ASCII (chat)."""

from __future__ import annotations

import random
import time

import win32api
import win32con
import win32gui

from mu_helper.logging_utils import write_log


def send_key_with_scancode(
    hwnd: int,
    vk_code: int,
    scan_code: int,
    focus_first: bool = True,
    press_delay: float = 0.05,
) -> bool:
    foreground = 0
    try:
        foreground = win32gui.GetForegroundWindow()
        if focus_first and foreground != hwnd:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
        win32api.keybd_event(vk_code, scan_code, 0, 0)
        time.sleep(press_delay)
        win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(press_delay)
        if focus_first and foreground and foreground != hwnd:
            win32gui.SetForegroundWindow(foreground)
        return True
    except Exception as e:
        write_log(f"Error enviando tecla: {e}", "ERROR")
        return False


def send_return_key(hwnd: int) -> bool:
    from mu_helper.config import SCANCODE_RETURN

    return send_key_with_scancode(hwnd, win32con.VK_RETURN, SCANCODE_RETURN, focus_first=True)


def send_home_key(hwnd: int) -> bool:
    from mu_helper.config import SCANCODE_HOME

    return send_key_with_scancode(hwnd, win32con.VK_HOME, SCANCODE_HOME, focus_first=True)


def send_i_key(hwnd: int) -> bool:
    from mu_helper.config import SCANCODE_I

    return send_key_with_scancode(hwnd, ord("I"), SCANCODE_I, focus_first=True)


def send_m_key(hwnd: int) -> bool:
    """Abre/cierra el mapa mundial (tecla M)."""
    return send_key_with_scancode(hwnd, ord("M"), 0x32, focus_first=True)


def send_tab_key(hwnd: int) -> bool:
    """Minimapa caminable (TAB)."""
    return send_key_with_scancode(hwnd, win32con.VK_TAB, 0x0F, focus_first=True)

def send_esc_key(hwnd: int) -> bool:
    """Cierra paneles/ventanas (ESC)."""
    return send_key_with_scancode(hwnd, win32con.VK_ESCAPE, 0x01, focus_first=True)


def send_left_ctrl_key(hwnd: int) -> bool:
    from mu_helper.config import SCANCODE_LCTRL

    return send_key_with_scancode(hwnd, win32con.VK_LCONTROL, SCANCODE_LCTRL, focus_first=True)


def send_q_key(hwnd: int, *, fast: bool = False) -> bool:
    from mu_helper.config import SCANCODE_Q, HEALER_KEY_PRESS_SEC

    delay = HEALER_KEY_PRESS_SEC if fast else 0.05
    return send_key_with_scancode(
        hwnd, ord("Q"), SCANCODE_Q, focus_first=not fast, press_delay=delay
    )


def send_w_key(hwnd: int, *, fast: bool = False) -> bool:
    from mu_helper.config import SCANCODE_W, HEALER_KEY_PRESS_SEC

    delay = HEALER_KEY_PRESS_SEC if fast else 0.05
    return send_key_with_scancode(
        hwnd, ord("W"), SCANCODE_W, focus_first=not fast, press_delay=delay
    )


def send_qw_potion_cycle(hwnd: int) -> bool:
    """Presiona Q y luego W en serie (no en paralelo), de forma rápida."""
    from mu_helper.config import HEALER_KEY_PRESS_SEC, SCANCODE_Q, SCANCODE_W

    foreground = 0
    try:
        foreground = win32gui.GetForegroundWindow()
        if foreground != hwnd:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.03)
        delay = HEALER_KEY_PRESS_SEC
        for vk, scan in ((ord("Q"), SCANCODE_Q), (ord("W"), SCANCODE_W)):
            win32api.keybd_event(vk, scan, 0, 0)
            time.sleep(delay)
            win32api.keybd_event(vk, scan, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(delay)
        if foreground and foreground != hwnd:
            win32gui.SetForegroundWindow(foreground)
        return True
    except Exception as e:
        write_log(f"Error enviando ciclo Q/W: {e}", "ERROR")
        return False


def send_pk_toggle(hwnd: int, repeats: int = 3, delay: float = 0.08) -> bool:
    ok = True
    for _ in range(max(1, repeats)):
        ok = send_left_ctrl_key(hwnd) and ok
        time.sleep(delay)
    return ok


def move_mouse_to(x: int, y: int, duration: float = 0.1, steps: int = 12) -> None:
    """Mueve el cursor de forma lineal (sin depender de pyautogui)."""
    cx, cy = win32api.GetCursorPos()
    if duration <= 0 or steps < 1:
        win32api.SetCursorPos((int(x), int(y)))
        return
    for i in range(1, steps + 1):
        t = i / steps
        nx = int(cx + (x - cx) * t)
        ny = int(cy + (y - cy) * t)
        win32api.SetCursorPos((nx, ny))
        time.sleep(duration / steps)


def click_at(
    x: int,
    y: int,
    pre_delay: float = 0.03,
    hold_down: float = 0.08,
    hold_up: float = 0.05,
) -> None:
    win32api.SetCursorPos((int(x), int(y)))
    time.sleep(pre_delay)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold_down)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(hold_up)


def type_chat_command(text: str, interval: float = 0.02) -> None:
    """Escribe texto en el foco actual (comando /pack). Requiere distribución de teclado compatible."""
    import pyautogui

    pyautogui.write(text, interval=interval)


def random_move_duration(bounds: tuple[float, float]) -> float:
    return random.uniform(bounds[0], bounds[1])
