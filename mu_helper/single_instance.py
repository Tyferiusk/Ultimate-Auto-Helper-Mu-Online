"""Una sola instancia del programa por sesión de Windows (mutex nombrado)."""

from __future__ import annotations

import atexit
import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateMutexW = kernel32.CreateMutexW
CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
CreateMutexW.restype = wintypes.HANDLE

GetLastError = kernel32.GetLastError
GetLastError.argtypes = ()
GetLastError.restype = wintypes.DWORD

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

_mutex_handle: wintypes.HANDLE | None = None
_released = False


def acquire_single_instance(mutex_name: str) -> bool:
    """
    Crea el mutex. Si ya existe otra instancia con el mismo nombre, devuelve False.
    El handle se libera al salir del proceso o llamando release_single_instance().
    """
    global _mutex_handle
    if _mutex_handle:
        return True
    h = CreateMutexW(None, False, mutex_name)
    if not h:
        return False
    if GetLastError() == ERROR_ALREADY_EXISTS:
        CloseHandle(h)
        return False
    _mutex_handle = h
    atexit.register(release_single_instance)
    return True


def release_single_instance() -> None:
    global _mutex_handle, _released
    if _released:
        return
    _released = True
    if _mutex_handle:
        try:
            CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None


def notify_duplicate_instance(title: str, message: str) -> None:
    """Aviso nativo sin QApplication (para salir antes de crear Qt)."""
    MB_ICONWARNING = 0x30
    ctypes.windll.user32.MessageBoxW(None, message, title, MB_ICONWARNING)
