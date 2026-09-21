"""Hilo principal de automatización."""

from __future__ import annotations

import json
import math
import os
import random
import re
import threading
import time
from typing import Any

import cv2
import mss
import numpy as np
import win32api
import win32con
import win32gui
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor

from mu_helper.config import (
    CITY_POPUP_TEMPLATE,
    CITY_POPUP_THRESHOLD,
    CITY_POPUP_REGION,
    CHAR_CENTER_RELATIVE,
    COORD_SCAN_REGION_A,
    COORD_SCAN_REGION_B,
    CONFIDENCE,
    DROP_WAIT,
    GROUND_REGION,
    INVENTORY_FULL_CHECK_INTERVAL,
    INVENTORY_OPEN_REGION,
    INVENTORY_OPEN_TEMPLATE,
    INVENTORY_OPEN_THRESHOLD,
    INVENTORY_REGION,
    JEWEL_CONFIDENCE,
    JEWELS,
    MANA_REGION,
    MANA_STABLE_SECONDS,
    MATCH_THRESHOLD,
    MAP_LIST_REGION,
    MAP_SELECTION_THRESHOLD,
    MINIMAP_OPEN_REGION,
    MINIMAP_OPEN_TEMPLATE,
    MINIMAP_OPEN_THRESHOLD,
    MERCHANT_OPEN_REGION,
    MERCHANT_OPEN_TEMPLATE,
    MAX_RETURN_STEPS_PER_WINDOW,
    MOVE_CLICK_OFFSET,
    MOVE_UNSTUCK_OFFSET,
    MOVE_STEP_PAUSE,
    NPC_OPEN_MAX_RETRIES,
    NPC_OPEN_RETRY_DELAY,
    NPC_POTION_SEARCH_REGION,
    NPC_POTION_THRESHOLD,
    NPC_POTION_TEMPLATE,
    SPOT_RETURN_STALL_RESTART_SEC,
    TELEGRAM_POLL_INTERVAL,
    WAIT_AFTER_TELEPORT,
    PACK_COOLDOWN,
    POPUP_OK_REGION,
    POPUP_OK_TEMPLATE,
    POPUP_OK_THRESHOLD,
    POTION_REGION,
    POTION_TEMPLATE,
    POTION_BUY_CLICK_DELAY,
    POTION_BUY_MAP_NAME,
    POTION_BUY_MANA_THRESHOLD,
    POTION_BUY_NAV_MAP_NAME,
    POTION_BUY_NPC_TARGET_COORDS,
    POTION_BUY_MANA_TEMPLATE,
    POTION_BUY_REGION,
    POTION_THRESHOLD,
    PRE_DROP_PAUSE,
    RETURN_UNSTUCK_LONG_CLICK_AFTER_SEC,
    GRAB_WAIT,
    MOVE_DURATION,
    REGION_OFFLINE,
    SLOT_VACIO_TEMPLATE,
    SLOT_VACIO_THRESHOLD,
    SKIP_IN_FIND_ITEMS,
    SPECIAL_MAP_ROUTES,
    map_template_filename,
)
from mu_helper.license import check_license, get_license_days_left, license_status_color_days
from mu_helper.logging_utils import write_log
from mu_helper.window_finder import get_game_windows
from mu_helper.win_input import (
    click_at,
    move_mouse_to,
    random_move_duration,
    send_home_key,
    send_i_key,
    send_m_key,
    send_pk_toggle,
    send_return_key,
    send_tab_key,
    type_chat_command,
)

_EASYOCR_READER: Any | None = None
_EASYOCR_INIT_FAILED = False

# Navegación minimapa: detección de obstáculos y desvío.
OBSTACLE_DARK_THRESHOLD = 55
OBSTACLE_RATIO_THRESHOLD = 0.35
DEVIATION_ANGLE_DEG = 30
SPOT_COORD_TOLERANCE = 2


def _ensure_easyocr_reader() -> Any | None:
    global _EASYOCR_READER, _EASYOCR_INIT_FAILED
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER
    if _EASYOCR_INIT_FAILED:
        return None
    try:
        import easyocr  # type: ignore

        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        return _EASYOCR_READER
    except Exception as e:
        write_log(f"easyocr init: {e}", "WARNING")
        _EASYOCR_INIT_FAILED = True
        return None


class MainThread(QThread):
    print_signal = Signal(str, QColor)
    scanning_signal = Signal(bool)
    finished_signal = Signal()
    license_expired_signal = Signal()

    def __init__(
        self,
        item_templates: dict[str, Any],
        helper_enabled: bool = False,
        cleaner_enabled: bool = False,
        pack_enabled: bool = False,
        telegram_enabled: bool = False,
        pk_mode_enabled: bool = False,
        window_configs: dict[int, dict[str, Any]] | None = None,
    ):
        super().__init__()
        self._running = True
        self.item_templates = item_templates
        self.helper_enabled = helper_enabled
        self.cleaner_enabled = cleaner_enabled
        self.pack_enabled = pack_enabled
        self.telegram_enabled = telegram_enabled
        self.pk_mode_enabled = pk_mode_enabled
        self.window_configs: dict[int, dict[str, Any]] = window_configs or {}

        self.template_offline = item_templates.get("offline.png")
        self.template_potion = item_templates.get(POTION_TEMPLATE)
        self.template_inv_open = item_templates.get(INVENTORY_OPEN_TEMPLATE)
        self.template_popup_ok = item_templates.get(POPUP_OK_TEMPLATE)
        self.template_city_popup = item_templates.get(CITY_POPUP_TEMPLATE)
        self.template_minimap_open = item_templates.get(MINIMAP_OPEN_TEMPLATE)
        self.template_slot_vacio = item_templates.get(SLOT_VACIO_TEMPLATE)
        self.template_npc_potions = item_templates.get(NPC_POTION_TEMPLATE)
        self.template_merchant_open = item_templates.get(MERCHANT_OPEN_TEMPLATE)
        self.template_buy_mana = item_templates.get(POTION_BUY_MANA_TEMPLATE)

        self.mana_state: dict[int, dict] = {}
        self.potion_notified: dict[int, bool] = {}
        self.death_notified: dict[int, bool] = {}
        self.inventory_full_notified: dict[int, bool] = {}
        self.last_pack_time: dict[tuple[int, str], float] = {}
        self.last_inv_full_check: dict[int, float] = {}
        self.current_window_title: str | None = None
        self.jewel_counts: dict[int, dict[str, int]] = {}
        self.recovering_to_spot: dict[int, bool] = {}
        self.pk_sent_for_recovery: dict[int, bool] = {}
        self.return_steps: dict[int, int] = {}
        self._death_teleport_done: dict[int, bool] = {}
        self._tab_open_for_spot: dict[int, bool] = {}

        self.telegram_token: str | None = None
        self.chat_id: str | None = None
        if telegram_enabled:
            self._load_telegram_config()

        self._sct: mss.mss | None = None
        self._potion_counter: dict[int, int] = {}

        self._next_license_check_mono: float = 0.0
        self._city_popup_retry_after: dict[int, float] = {}
        self._paused_for_recovery: dict[int, bool] = {}
        self._telegram_update_offset: int = 0
        self._last_known_coords: dict[int, tuple[int, int]] = {}
        self._last_move_direction: dict[int, str] = {}
        self._stuck_since: dict[int, float] = {}
        self._last_potion_check_mono: dict[int, float] = {}
        self._global_pause_log_mono: float = 0.0
        self._buying_potions: dict[int, bool] = {}
        self._buy_notified: dict[int, bool] = {}
        self._buy_stage: dict[int, str] = {}
        self._buy_teleport_attempts: dict[int, int] = {}
        self._buy_npc_open_attempts: dict[int, int] = {}
        self._coord_history: dict[int, list[tuple[int, int]]] = {}
        self._ocr_bootstrap_reads: dict[int, list[tuple[int, int]]] = {}
        self._last_ocr_no_read_log_mono: dict[int, float] = {}
        self._ocr_no_read_count: dict[int, int] = {}
        self._ocr_debug_enabled: bool = True
        self._last_direction_change_mono: dict[int, float] = {}
        self._direction_inversion: dict[int, dict[str, bool]] = {}
        self._move_feedback: dict[int, dict[str, Any]] = {}
        self._detour_steps_remaining: dict[int, int] = {}
        self._detour_direction: dict[int, str] = {}
        self._detour_turn_toggle: dict[int, bool] = {}

    def _load_telegram_config(self) -> None:
        from mu_helper.config import TELEGRAM_CONFIG_FILE
        import json

        if os.path.exists(TELEGRAM_CONFIG_FILE):
            try:
                with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.telegram_token = config.get("token")
                    self.chat_id = config.get("chat_id")
            except Exception as e:
                write_log(f"Telegram config: {e}", "WARNING")

    def _get_window_return_config(
        self,
        hwnd: int,
        title: str,
    ) -> tuple[bool, tuple[int, int] | None, str, str, dict[str, Any]]:
        cfg = self.window_configs.get(hwnd) or self.window_configs.get(str(hwnd)) or {}
        enabled = bool(cfg.get("return_enabled", False))
        coords = cfg.get("target_coords")
        map_name = str(cfg.get("target_map") or "").strip()
        character_name = str(cfg.get("character_name") or "").strip()
        buy_cfg = {
            "enabled": bool(cfg.get("auto_buy_potions_enabled", False)),
            "buy_mana": bool(cfg.get("buy_mana_enabled", True)),
            "mana_clicks": int(cfg.get("buy_mana_clicks", 10) or 0),
        }
        if not (isinstance(coords, list) and len(coords) == 2):
            return enabled, None, map_name, character_name, buy_cfg
        try:
            return enabled, (int(coords[0]), int(coords[1])), map_name, character_name, buy_cfg
        except Exception:
            write_log(f"Config coords inválida para {hwnd} ({title})", "WARNING")
            return enabled, None, map_name, character_name, buy_cfg

    def _window_label(self, display_title: str, character_name: str) -> str:
        return f"{character_name} | {display_title}" if character_name else display_title

    def _is_spot_reached(self, current: tuple[int, int], target: tuple[int, int]) -> bool:
        return abs(current[0] - target[0]) <= SPOT_COORD_TOLERANCE and abs(current[1] - target[1]) <= SPOT_COORD_TOLERANCE

    def _extract_text(self, img_bgr: np.ndarray) -> str:
        try:
            reader = _ensure_easyocr_reader()
            if reader is None:
                return ""
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            _ok, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results = reader.readtext(th, detail=0, paragraph=True)
            if not results:
                return ""
            return " ".join(str(r) for r in results).lower().strip()
        except Exception:
            return ""

    def run(self) -> None:
        try:
            self._sct = mss.mss()
        except Exception as e:
            self.print_signal.emit(f"No se pudo iniciar captura: {e}", QColor(255, 0, 0))
            self.finished_signal.emit()
            return

        try:
            if not check_license():
                self.print_signal.emit("Licencia no válida.", QColor(255, 0, 0))
                self.finished_signal.emit()
                return

            self.print_signal.emit("Ultimate Mu Helper en ejecución", QColor(0, 128, 255))
            days_left = get_license_days_left()
            if days_left is not None:
                hex_c, _ = license_status_color_days(days_left)
                qc = QColor(hex_c)
                if not qc.isValid():
                    qc = QColor(0, 128, 255)
                self.print_signal.emit(f"Días restantes de licencia: {days_left}", qc)
            if self.helper_enabled:
                self.print_signal.emit("Auto Helper activado", QColor(0, 200, 200))
            if self.cleaner_enabled:
                self.print_signal.emit("Limpieza de inventario activada", QColor(200, 200, 0))
            if self.pack_enabled:
                self.print_signal.emit("Empaquetado de joyas activado", QColor(255, 215, 0))
            if self.telegram_enabled:
                if self.telegram_token:
                    self.print_signal.emit("Notificaciones Telegram activadas", QColor(0, 200, 0))
                else:
                    self.print_signal.emit("Telegram activado pero no configurado", QColor(255, 165, 0))
            if self.window_configs:
                enabled_count = sum(1 for c in self.window_configs.values() if c.get("return_enabled"))
                self.print_signal.emit(
                    f"Retorno por ventana activo en {enabled_count} ventana(s)",
                    QColor(148, 226, 213),
                )
            if self.pk_mode_enabled:
                self.print_signal.emit("Modo PK al revivir: activado (Ctrl izq x3)", QColor(250, 179, 135))

            self._next_license_check_mono = time.monotonic() + 43200.0
            next_tg_poll = time.monotonic() + 3.0

            while self._running:
                now_mono = time.monotonic()
                if now_mono >= self._next_license_check_mono:
                    self._next_license_check_mono = now_mono + 43200.0
                    if not check_license():
                        self.print_signal.emit(
                            "Licencia inválida o caducada (re-verificación 12 h). Deteniendo.",
                            QColor(255, 0, 0),
                        )
                        self.license_expired_signal.emit()
                        self._running = False
                        break

                windows = get_game_windows()
                if self.telegram_enabled and self.telegram_token and now_mono >= next_tg_poll:
                    next_tg_poll = now_mono + TELEGRAM_POLL_INTERVAL
                    self._poll_telegram_commands(windows)
                if not windows:
                    self.print_signal.emit("Esperando ventanas del juego…", QColor(255, 165, 0))
                    self.scanning_signal.emit(False)
                    time.sleep(3)
                    continue

                recovery_active_global = any(self.recovering_to_spot.get(hwnd, False) for hwnd, _ in windows)
                cycle_active_global = recovery_active_global or any(
                    self._buying_potions.get(hwnd, False) for hwnd, _ in windows
                )
                if cycle_active_global and (now_mono - self._global_pause_log_mono) >= 2.0:
                    self._global_pause_log_mono = now_mono
                    self.print_signal.emit(
                        "Ciclo activo (retorno/compra): otras ventanas en pausa hasta que termine",
                        QColor(250, 179, 135),
                    )

                for hwnd, win_index in windows:
                    if not self._running:
                        break

                    other_holds_cycle = False
                    for h_other, _ in windows:
                        if h_other == hwnd:
                            continue
                        if self.recovering_to_spot.get(h_other, False) or self._buying_potions.get(h_other, False):
                            other_holds_cycle = True
                            break
                    if other_holds_cycle:
                        continue

                    title = win32gui.GetWindowText(hwnd)
                    display_title = f"[Ventana {win_index}] {title}"
                    return_enabled, target_coords, respawn_map_name, character_name, buy_cfg = self._get_window_return_config(
                        hwnd, display_title
                    )
                    win_label = self._window_label(display_title, character_name)
                    if self.current_window_title != display_title:
                        self.print_signal.emit(f"Ventana activa: {win_label}", QColor(0, 0, 200))
                        self.current_window_title = display_title

                    self.focus_window(hwnd)
                    time.sleep(0.2)

                    if self.recovering_to_spot.get(hwnd, False):
                        if not self._paused_for_recovery.get(hwnd, False):
                            self._paused_for_recovery[hwnd] = True
                            self.print_signal.emit(
                                f"{win_label} — helper/limpieza pausados por retorno",
                                QColor(250, 179, 135),
                            )
                        done = self.handle_return_to_spot(
                            hwnd,
                            win_label,
                            target_coords=target_coords,
                            respawn_map_name=respawn_map_name,
                        )
                        if done:
                            self.recovering_to_spot[hwnd] = False
                            self.pk_sent_for_recovery[hwnd] = False
                            self.return_steps[hwnd] = 0
                            self.death_notified[hwnd] = False
                            self._death_teleport_done.pop(hwnd, None)
                            self._tab_open_for_spot.pop(hwnd, None)
                            self._paused_for_recovery[hwnd] = False
                            self.print_signal.emit(
                                f"{win_label} — spot recuperado, reanudando helper/cleaner",
                                QColor(166, 227, 161),
                            )
                        time.sleep(0.2)
                        continue

                    if self._buying_potions.get(hwnd, False):
                        if not self._buy_notified.get(hwnd, False):
                            self._buy_notified[hwnd] = True
                            self.print_signal.emit(
                                f"{win_label} — compra de pociones en curso, pausando acciones normales",
                                QColor(250, 179, 135),
                            )
                        bought = self.handle_buy_potions(
                            hwnd,
                            win_label,
                            buy_cfg,
                        )
                        if bought:
                            self._buying_potions[hwnd] = False
                            self._buy_notified[hwnd] = False
                            self._buy_stage.pop(hwnd, None)
                            self._buy_teleport_attempts.pop(hwnd, None)
                            self._buy_npc_open_attempts.pop(hwnd, None)
                            if return_enabled and target_coords is not None:
                                self.recovering_to_spot[hwnd] = True
                                self.pk_sent_for_recovery[hwnd] = False
                                self.return_steps[hwnd] = 0
                                self._death_teleport_done[hwnd] = False
                                self._tab_open_for_spot[hwnd] = False
                                self.print_signal.emit(
                                    f"{win_label} — compra completada, regresando al spot",
                                    QColor(166, 227, 161),
                                )
                        time.sleep(0.2)
                        continue

                    if recovery_active_global:
                        # Si alguna ventana está recuperando spot, pausamos el resto de funciones.
                        continue

                    rect = win32gui.GetWindowRect(hwnd)
                    win_left, win_top = rect[0], rect[1]

                    if self.helper_enabled:
                        if self.is_city_popup_present(hwnd):
                            self.print_signal.emit(
                                f"{win_label} — popup de ciudad detectado: personaje muerto, cerrando con ENTER",
                                QColor(255, 0, 0),
                            )
                            popup_closed = self.dismiss_city_popup(hwnd, win_label)
                            write_log("Ciudad detectada (popup), personaje muerto, iniciando retorno al spot")
                            if not popup_closed:
                                # Sin confirmación de cierre: no avanzamos para evitar abrir M con popup encima.
                                time.sleep(0.4)
                                continue
                            # Notificación única por muerte (se resetea cuando se completa el retorno).
                            if not self.death_notified.get(hwnd, False):
                                self.death_notified[hwnd] = True
                                if self.telegram_enabled and self.telegram_token:
                                    self.send_telegram(
                                        f"Tu personaje ha muerto.\nVentana: {win_label}"
                                    )
                            if return_enabled and target_coords is not None:
                                self.recovering_to_spot[hwnd] = True
                                self.pk_sent_for_recovery[hwnd] = False
                                self.return_steps[hwnd] = 0
                                self._death_teleport_done[hwnd] = False
                                self._tab_open_for_spot[hwnd] = False
                                target_map = respawn_map_name or "mapa no definido"
                                self.print_signal.emit(
                                    f"{win_label} — Volviendo al spot en {target_map}",
                                    QColor(250, 179, 135),
                                )
                                if self.telegram_enabled and self.telegram_token:
                                    self.send_telegram(
                                        f"Volviendo al spot en {target_map}.\nVentana: {win_label}"
                                    )
                                time.sleep(0.5)
                                continue
                            self._city_popup_retry_after[hwnd] = time.time() + 2.0
                            time.sleep(0.3)
                            continue
                        retry_at = self._city_popup_retry_after.get(hwnd, 0.0)
                        if retry_at and time.time() >= retry_at:
                            self.ensure_inventory_closed_for_helper(hwnd, win_label)
                            send_home_key(hwnd)
                            self.print_signal.emit(
                                f"{win_label} — reintento HOME tras popup de ciudad",
                                QColor(250, 179, 135),
                            )
                            self._city_popup_retry_after[hwnd] = 0.0
                            time.sleep(0.4)
                            continue
                        if self.is_helper_offline(hwnd):
                            self.print_signal.emit(f"Helper OFFLINE en {win_label}", QColor(255, 0, 0))
                            self.ensure_inventory_closed_for_helper(hwnd, win_label)
                            send_home_key(hwnd)
                            self.print_signal.emit("  HOME enviado", QColor(0, 200, 0))
                            time.sleep(0.5)
                            continue
                        self.check_mana_stability(hwnd, win_label)

                    if self.cleaner_enabled or self.pack_enabled:
                        if self.handle_popup_ok(hwnd, win_label):
                            time.sleep(0.5)
                            continue

                    need_inventory = self.cleaner_enabled or self.pack_enabled
                    if need_inventory:
                        if self.is_minimap_open(hwnd):
                            self.print_signal.emit(
                                f"{win_label} — cerrando TAB para validar inventario",
                                QColor(148, 226, 213),
                            )
                            self.ensure_minimap_closed(hwnd, win_label)
                            time.sleep(0.2)
                        if not self.is_inventory_open(hwnd):
                            self.print_signal.emit(
                                f"Inventario cerrado en {win_label}, abriendo…",
                                QColor(200, 200, 0),
                            )
                            send_i_key(hwnd)
                            time.sleep(0.5)
                            self.jewel_counts[hwnd] = {}
                            continue

                    self.check_potion(hwnd, win_label, buy_cfg)
                    if self._buying_potions.get(hwnd, False):
                        continue
                    if self.telegram_enabled and need_inventory:
                        self.check_inventory_full(hwnd, win_label)

                    if need_inventory and self.is_inventory_open(hwnd):
                        search_left = win_left + INVENTORY_REGION[0]
                        search_top = win_top + INVENTORY_REGION[1]
                        abs_region = (
                            search_left,
                            search_top,
                            INVENTORY_REGION[2],
                            INVENTORY_REGION[3],
                        )
                        self.scanning_signal.emit(True)

                        jewel_summary = []
                        for jewel_file in JEWELS:
                            jewel_name = os.path.splitext(jewel_file)[0]
                            count = self.count_jewel_occurrences(jewel_file, abs_region)
                            self.jewel_counts.setdefault(hwnd, {})[jewel_name] = count
                            if count > 0:
                                jewel_summary.append(f"{jewel_name.title()} x{count}")
                        if jewel_summary:
                            self.print_signal.emit(
                                f"{win_label} — Joyas: {', '.join(jewel_summary)}",
                                QColor(100, 200, 255),
                            )
                        else:
                            self.print_signal.emit(
                                f"{win_label} — Joyas: ninguna",
                                QColor(150, 150, 150),
                            )

                        if self.cleaner_enabled:
                            items = self.find_items(hwnd, INVENTORY_REGION, include_jewels=False)
                            if items:
                                item_names = [item[0].replace("_", " ").title() for item in items]
                                self.print_signal.emit(
                                    f"{win_label} — Objetos a limpiar: {', '.join(item_names)}",
                                    QColor(255, 200, 100),
                                )
                            else:
                                self.print_signal.emit(
                                    f"{win_label} — Objetos a limpiar: ninguno",
                                    QColor(150, 150, 150),
                                )

                        if self.cleaner_enabled:
                            while self._running and self.is_inventory_open(hwnd):
                                items = self.find_items(hwnd, INVENTORY_REGION, include_jewels=False)
                                if not items:
                                    break
                                item_name, (left, top, w, h) = items[0]
                                center_x = left + w // 2
                                center_y = top + h // 2
                                display = item_name.replace("_", " ").title()
                                self.print_signal.emit(f"  {display}", QColor(255, 165, 0))

                                target_x = random.randint(
                                    win_left + GROUND_REGION[0],
                                    win_left + GROUND_REGION[0] + GROUND_REGION[2],
                                )
                                target_y = random.randint(
                                    win_top + GROUND_REGION[1],
                                    win_top + GROUND_REGION[1] + GROUND_REGION[3],
                                )

                                self.focus_window(hwnd)
                                time.sleep(0.05)

                                win32api.SetCursorPos((center_x, center_y))
                                time.sleep(0.5)
                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                time.sleep(0.08)
                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                time.sleep(GRAB_WAIT + random.uniform(-0.03, 0.03))

                                move_time = random_move_duration(MOVE_DURATION)
                                move_mouse_to(target_x, target_y, duration=move_time)
                                time.sleep(PRE_DROP_PAUSE)

                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                time.sleep(0.08)
                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                time.sleep(DROP_WAIT + random.uniform(-0.05, 0.05))

                                self.print_signal.emit(f"  → {display} al suelo", QColor(34, 139, 34))

                        if self.pack_enabled:
                            for jewel_file in JEWELS:
                                jewel_name = os.path.splitext(jewel_file)[0]
                                count = self.jewel_counts.get(hwnd, {}).get(jewel_name, 0)
                                if count >= 10:
                                    key = (hwnd, jewel_name)
                                    now = time.monotonic()
                                    if now - self.last_pack_time.get(key, 0) >= PACK_COOLDOWN:
                                        self.print_signal.emit(
                                            f"{win_label} — {jewel_name.title()} x{count} → empaquetando",
                                            QColor(255, 215, 0),
                                        )
                                        if self.pack_jewel(hwnd, jewel_name):
                                            self.print_signal.emit("  /pack enviado", QColor(0, 200, 0))
                                            self.last_pack_time[key] = now
                                            self.jewel_counts[hwnd][jewel_name] = 0
                                        else:
                                            self.print_signal.emit("  Fallo al enviar comando", QColor(255, 0, 0))

                        self.scanning_signal.emit(False)

                    time.sleep(0.2)
        finally:
            if self._sct is not None:
                try:
                    self._sct.close()
                except Exception:
                    pass
                self._sct = None

        self.scanning_signal.emit(False)
        self.print_signal.emit("Proceso detenido", QColor(200, 0, 0))
        self.finished_signal.emit()

    def stop(self) -> None:
        self._running = False

    def focus_window(self, hwnd: int) -> None:
        try:
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.05)
        except Exception:
            pass

    def capture_region(self, hwnd: int, region: tuple[int, int, int, int]) -> np.ndarray | None:
        if self._sct is None:
            return None
        try:
            rect = win32gui.GetWindowRect(hwnd)
            abs_left = rect[0] + region[0]
            abs_top = rect[1] + region[1]
            monitor = {
                "left": abs_left,
                "top": abs_top,
                "width": region[2],
                "height": region[3],
            }
            img = np.array(self._sct.grab(monitor))
            # mss devuelve BGRA; cv2.imread y matchTemplate esperan BGR en plantillas de color
            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            write_log(f"capture_region: {e}", "WARNING")
            return None

    def is_template_present(
        self,
        hwnd: int,
        region: tuple[int, int, int, int],
        template: np.ndarray | None,
        threshold: float,
    ) -> bool:
        if template is None:
            return False
        img = self.capture_region(hwnd, region)
        if img is None:
            return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        max_val = float(np.max(result))
        return max_val >= threshold

    def is_inventory_open(self, hwnd: int) -> bool:
        return self.is_template_present(
            hwnd,
            INVENTORY_OPEN_REGION,
            self.template_inv_open,
            INVENTORY_OPEN_THRESHOLD,
        )

    def ensure_inventory_closed_for_helper(self, hwnd: int, display_title: str) -> None:
        if self.is_inventory_open(hwnd):
            self.print_signal.emit(
                f"Cerrando inventario para reactivar helper en {display_title}",
                QColor(200, 200, 0),
            )
            send_i_key(hwnd)
            time.sleep(0.5)

    def is_minimap_open(self, hwnd: int) -> bool:
        return self.is_template_present(
            hwnd,
            MINIMAP_OPEN_REGION,
            self.template_minimap_open,
            MINIMAP_OPEN_THRESHOLD,
        )

    def ensure_minimap_open(
        self,
        hwnd: int,
        display_title: str | None = None,
        max_attempts: int = 3,
    ) -> bool:
        """Garantiza que el minimapa quede ABIERTO. Devuelve True si se confirma."""
        for attempt in range(max_attempts):
            if self.is_minimap_open(hwnd):
                self._tab_open_for_spot[hwnd] = True
                return True
            send_tab_key(hwnd)
            time.sleep(0.30 if attempt == 0 else 0.20)
        ok = self.is_minimap_open(hwnd)
        self._tab_open_for_spot[hwnd] = ok
        if not ok and display_title is not None:
            self.print_signal.emit(
                f"{display_title} — no se pudo abrir el minimapa tras {max_attempts} intentos",
                QColor(243, 139, 168),
            )
        return ok

    def ensure_minimap_closed(
        self,
        hwnd: int,
        display_title: str | None = None,
        max_attempts: int = 3,
    ) -> bool:
        """Garantiza que el minimapa quede CERRADO. Devuelve True si se confirma."""
        for attempt in range(max_attempts):
            if not self.is_minimap_open(hwnd):
                self._tab_open_for_spot[hwnd] = False
                return True
            send_tab_key(hwnd)
            time.sleep(0.25 if attempt == 0 else 0.20)
        ok = not self.is_minimap_open(hwnd)
        self._tab_open_for_spot[hwnd] = not ok
        if not ok and display_title is not None:
            self.print_signal.emit(
                f"{display_title} — no se pudo cerrar el minimapa tras {max_attempts} intentos",
                QColor(243, 139, 168),
            )
        return ok

    def dismiss_city_popup(
        self,
        hwnd: int,
        display_title: str,
        max_attempts: int = 5,
        wait_after_enter: float = 0.45,
    ) -> bool:
        """Cierra el popup 'auto attack outside the city' y confirma que se haya ido."""
        for attempt in range(1, max_attempts + 1):
            if not self.is_city_popup_present(hwnd):
                return True
            send_return_key(hwnd)
            time.sleep(wait_after_enter)
            if not self.is_city_popup_present(hwnd):
                if attempt > 1:
                    self.print_signal.emit(
                        f"{display_title} — popup de ciudad cerrado tras {attempt} intentos",
                        QColor(148, 226, 213),
                    )
                return True
        self.print_signal.emit(
            f"{display_title} — popup de ciudad sigue visible tras {max_attempts} intentos",
            QColor(243, 139, 168),
        )
        return False

    def is_city_popup_present(self, hwnd: int) -> bool:
        if self.template_city_popup is not None:
            if self.is_template_present(hwnd, CITY_POPUP_REGION, self.template_city_popup, CITY_POPUP_THRESHOLD):
                return True
        img = self.capture_region(hwnd, CITY_POPUP_REGION)
        if img is None:
            return False
        txt = self._extract_text(img)
        if not txt:
            return False
        return (
            ("auto attack" in txt and "outside the city" in txt)
            or ("activated outside" in txt and "city" in txt)
        )

    def handle_popup_ok(self, hwnd: int, display_title: str) -> bool:
        if not self.is_template_present(
            hwnd,
            POPUP_OK_REGION,
            self.template_popup_ok,
            POPUP_OK_THRESHOLD,
        ):
            return False
        self.print_signal.emit(
            f"Popup inventario en {display_title}",
            QColor(255, 165, 0),
        )
        rect = win32gui.GetWindowRect(hwnd)
        abs_left = rect[0] + POPUP_OK_REGION[0] + POPUP_OK_REGION[2] // 2
        abs_top = rect[1] + POPUP_OK_REGION[1] + POPUP_OK_REGION[3] // 2
        click_at(abs_left, abs_top)
        time.sleep(0.5)
        send_i_key(hwnd)
        time.sleep(0.5)
        send_home_key(hwnd)
        self.print_signal.emit(f"  Popup gestionado, HOME en {display_title}", QColor(0, 200, 0))
        return True

    def check_inventory_full(self, hwnd: int, display_title: str) -> None:
        now = time.monotonic()
        last = self.last_inv_full_check.get(hwnd, 0)
        if now - last < INVENTORY_FULL_CHECK_INTERVAL:
            return
        self.last_inv_full_check[hwnd] = now

        if self.template_slot_vacio is None:
            return
        img = self.capture_region(hwnd, INVENTORY_REGION)
        if img is None:
            return
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, self.template_slot_vacio, cv2.TM_CCOEFF_NORMED)
        max_val = float(np.max(result))
        if max_val < 0.01:
            self.print_signal.emit(
                f"{display_title} — slot vacío similitud: {max_val:.3f} (inventario lleno probable)",
                QColor(150, 150, 150),
            )
        else:
            self.print_signal.emit(
                f"{display_title} — slot vacío similitud: {max_val:.3f} (umbral {SLOT_VACIO_THRESHOLD})",
                QColor(150, 150, 150),
            )
        if max_val < SLOT_VACIO_THRESHOLD:
            if not self.inventory_full_notified.get(hwnd, False):
                self.print_signal.emit(f"Inventario lleno en {display_title}", QColor(255, 165, 0))
                if self.telegram_enabled and self.telegram_token:
                    msg = f"Inventario lleno.\nVentana: {display_title}"
                    self.send_telegram(msg)
                self.inventory_full_notified[hwnd] = True
        else:
            if self.inventory_full_notified.get(hwnd, False):
                self.inventory_full_notified[hwnd] = False

    def is_helper_offline(self, hwnd: int) -> bool:
        if self.template_offline is None:
            return False
        region_img = self.capture_region(hwnd, REGION_OFFLINE)
        if region_img is None:
            return False
        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, self.template_offline, cv2.TM_CCOEFF_NORMED)
        max_val = float(np.max(result))
        return max_val > MATCH_THRESHOLD

    def frames_similar(
        self,
        img1: np.ndarray | None,
        img2: np.ndarray | None,
        threshold: float = 0.99,
    ) -> bool:
        if img1 is None or img2 is None:
            return False
        try:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))
            result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
            return float(result[0][0]) >= threshold
        except Exception:
            return False

    def check_mana_stability(self, hwnd: int, display_title: str) -> None:
        now = time.monotonic()
        if hwnd not in self.mana_state:
            self.mana_state[hwnd] = {
                "last_img": None,
                "stable_since": None,
                "cooldown_until": 0.0,
            }
        state = self.mana_state[hwnd]
        if now < float(state.get("cooldown_until", 0.0)):
            return
        current_img = self.capture_region(hwnd, MANA_REGION)
        if current_img is None:
            return
        if state["last_img"] is None:
            state["last_img"] = current_img
            state["stable_since"] = None
            return
        if self.frames_similar(state["last_img"], current_img):
            if state.get("stable_since") is None:
                state["stable_since"] = now
            stable_time = now - float(state["stable_since"])
            if stable_time >= MANA_STABLE_SECONDS:
                self.print_signal.emit(f"{display_title} — maná estable, enviando HOME", QColor(255, 165, 0))
                self.ensure_inventory_closed_for_helper(hwnd, display_title)
                send_home_key(hwnd)
                state["cooldown_until"] = now + 10.0
                state["stable_since"] = None
                state["last_img"] = current_img
        else:
            state["stable_since"] = None
        state["last_img"] = current_img

    def check_potion(self, hwnd: int, display_title: str, buy_cfg: dict[str, Any]) -> None:
        if self.template_potion is None:
            return
        now = time.monotonic()
        last = self._last_potion_check_mono.get(hwnd, 0.0)
        if now - last < 2.0:
            return
        self._last_potion_check_mono[hwnd] = now
        region_img = self.capture_region(hwnd, POTION_REGION)
        if region_img is None:
            return
        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, self.template_potion, cv2.TM_CCOEFF_NORMED)
        max_val = float(np.max(result))
        self.print_signal.emit(
            f"{display_title} — poción similitud: {max_val:.3f} (umbral {POTION_THRESHOLD})",
            QColor(150, 150, 150),
        )
        if max_val >= POTION_THRESHOLD:
            if not self.potion_notified.get(hwnd, False):
                self.print_signal.emit(f"Sin pociones en {display_title}", QColor(255, 165, 0))
                if self.telegram_enabled and self.telegram_token:
                    msg = f"Sin pociones de maná.\nVentana: {display_title}"
                    self.send_telegram(msg)
                if bool(buy_cfg.get("enabled", False)):
                    self._buying_potions[hwnd] = True
                    self._buy_notified[hwnd] = False
                    self._buy_stage[hwnd] = "to_shop_map"
                    self._buy_teleport_attempts[hwnd] = 0
                    self._buy_npc_open_attempts[hwnd] = 0
                    self.recovering_to_spot[hwnd] = False
                    self._death_teleport_done[hwnd] = False
                    self.return_steps[hwnd] = 0
                    if self.is_minimap_open(hwnd):
                        self.ensure_minimap_closed(hwnd, display_title)
                    self.print_signal.emit(
                        f"{display_title} — iniciando compra automática de pociones",
                        QColor(243, 139, 168),
                    )
                    if self.telegram_enabled and self.telegram_token:
                        self.send_telegram(
                            f"Sin pociones de maná. Iniciando compra automática.\nVentana: {display_title}"
                        )
                else:
                    self.print_signal.emit(
                        f"{display_title} — compra automática desactivada, esperando intervención manual",
                        QColor(243, 139, 168),
                    )
                self.potion_notified[hwnd] = True
        else:
            if self.potion_notified.get(hwnd, False):
                self.potion_notified[hwnd] = False

    def _match_template_in_region(
        self,
        hwnd: int,
        region: tuple[int, int, int, int],
        template: np.ndarray | None,
        threshold: float = 0.72,
        template_name: str | None = None,
        display_title: str | None = None,
    ) -> tuple[int, int, float] | None:
        if template is None:
            return None
        img = self.capture_region(hwnd, region)
        if img is None:
            return None
        th, tw = template.shape[:2]
        ih, iw = img.shape[:2]
        if th > ih or tw > iw:
            return None
        if len(template.shape) == 2:
            search = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            use_t = template
        else:
            search = img
            use_t = template
        res = cv2.matchTemplate(search, use_t, cv2.TM_CCOEFF_NORMED)
        _min_v, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
        if display_title and template_name:
            self.print_signal.emit(
                f"{display_title} — template {template_name} sim={max_val:.3f} (umbral {threshold:.2f})",
                QColor(150, 150, 150),
            )
        if max_val < threshold:
            return None
        rect = win32gui.GetWindowRect(hwnd)
        ml, mt = max_loc
        abs_x = rect[0] + region[0] + ml + tw // 2
        abs_y = rect[1] + region[1] + mt + th // 2
        return abs_x, abs_y, float(max_val)

    def handle_buy_potions(
        self,
        hwnd: int,
        display_title: str,
        buy_cfg: dict[str, Any],
    ) -> bool:
        if not bool(buy_cfg.get("enabled", False)):
            return True
        buy_mana = bool(buy_cfg.get("buy_mana", True))
        mana_clicks = int(buy_cfg.get("mana_clicks", 0) or 0)
        if not (buy_mana and mana_clicks > 0):
            self.print_signal.emit(
                f"{display_title} — compra automática sin cantidades válidas, cancelada",
                QColor(243, 139, 168),
            )
            return True

        stage = self._buy_stage.get(hwnd, "to_shop_map")

        if stage == "to_shop_map":
            self.ensure_inventory_closed_for_helper(hwnd, display_title)
            if self.teleport_to_map(hwnd, display_title, POTION_BUY_MAP_NAME):
                self._last_known_coords.pop(hwnd, None)
                self._buy_stage[hwnd] = "to_npc"
                self._buy_teleport_attempts[hwnd] = 0
                return False
            attempts = self._buy_teleport_attempts.get(hwnd, 0) + 1
            self._buy_teleport_attempts[hwnd] = attempts
            if attempts >= 3:
                # Evita bucle de error si el teleport ya ocurrió pero el template no matchea en ese frame.
                self.print_signal.emit(
                    f"{display_title} — asumiendo {POTION_BUY_MAP_NAME} activo tras {attempts} intentos, continuando al NPC",
                    QColor(250, 179, 135),
                )
                self._buy_stage[hwnd] = "to_npc"
                self._buy_teleport_attempts[hwnd] = 0
            return False

        if stage == "to_npc":
            reached_npc_area = self.navigate_to_spot_with_tab(
                hwnd,
                display_title,
                POTION_BUY_NPC_TARGET_COORDS,
                POTION_BUY_NAV_MAP_NAME,
            )
            if not reached_npc_area:
                return False
            if self.is_minimap_open(hwnd):
                self.ensure_minimap_closed(hwnd, display_title)
                time.sleep(0.2)
            self._buy_stage[hwnd] = "open_merchant"
            self._buy_npc_open_attempts[hwnd] = 0
            return False

        if stage == "open_merchant":
            open_hit = self._match_template_in_region(
                hwnd,
                MERCHANT_OPEN_REGION,
                self.template_merchant_open,
                threshold=0.68,
                template_name=MERCHANT_OPEN_TEMPLATE,
                display_title=display_title,
            )
            if open_hit is not None:
                self._buy_stage[hwnd] = "buy_items"
                return False
            npc_hit = self._match_template_in_region(
                hwnd,
                NPC_POTION_SEARCH_REGION,
                self.template_npc_potions,
                threshold=NPC_POTION_THRESHOLD,
                template_name=NPC_POTION_TEMPLATE,
                display_title=display_title,
            )
            if npc_hit is not None:
                click_at(npc_hit[0], npc_hit[1])
                self.print_signal.emit(
                    f"{display_title} — click en NPC de pociones (sim {npc_hit[2]:.2f})",
                    QColor(137, 180, 250),
                )
            attempts = self._buy_npc_open_attempts.get(hwnd, 0) + 1
            self._buy_npc_open_attempts[hwnd] = attempts
            if attempts >= 3:
                self.print_signal.emit(
                    f"{display_title} — merchant no abrió, reiniciando viaje a {POTION_BUY_MAP_NAME}",
                    QColor(243, 139, 168),
                )
                self._buy_stage[hwnd] = "to_shop_map"
                self._buy_npc_open_attempts[hwnd] = 0
            time.sleep(NPC_OPEN_RETRY_DELAY)
            return False

        # stage == "buy_items"

        def _buy_clicks(template: np.ndarray | None, total: int, name: str, threshold: float) -> int:
            hit: tuple[int, int, float] | None = None
            for attempt in range(1, 16):
                hit = self._match_template_in_region(
                    hwnd,
                    POTION_BUY_REGION,
                    template,
                    threshold=threshold,
                    template_name=name,
                    display_title=display_title,
                )
                if hit is not None:
                    break
                if attempt % 5 == 0:
                    self.print_signal.emit(
                        f"{display_title} — reintento {attempt}/15 buscando {name}",
                        QColor(243, 139, 168),
                    )
                time.sleep(0.15)
            if hit is None:
                self.print_signal.emit(
                    f"{display_title} — no se encontró {name} en región de compra",
                    QColor(243, 139, 168),
                )
                return 0
            cx, cy, sim = hit
            self.print_signal.emit(
                f"{display_title} — {name} detectada en centro ({cx},{cy}) sim={sim:.2f}; clicks={total}",
                QColor(137, 180, 250),
            )
            done = 0
            while done < total and self._running:
                click_at(cx, cy)
                done += 1
                self.print_signal.emit(
                    f"{display_title} — {name} click {done}/{total}",
                    QColor(166, 227, 161),
                )
                time.sleep(POTION_BUY_CLICK_DELAY)
            return done

        self.print_signal.emit(f"{display_title} — iniciando compra de maná", QColor(137, 180, 250))
        bought_mana = _buy_clicks(
            self.template_buy_mana,
            mana_clicks,
            POTION_BUY_MANA_TEMPLATE,
            threshold=0.66,
        ) if buy_mana else 0
        self.print_signal.emit(
            f"{display_title} — compra completada (maná {bought_mana}/{mana_clicks})",
            QColor(166, 227, 161),
        )
        # Paso 7: cerrar tienda/inventario antes de volver al spot.
        send_i_key(hwnd)
        time.sleep(0.25)
        if self.is_inventory_open(hwnd):
            send_i_key(hwnd)
            time.sleep(0.2)
        self.print_signal.emit(
            f"{display_title} — tienda/inventario cerrados (tecla I), reanudando retorno",
            QColor(148, 226, 213),
        )
        if self.telegram_enabled and self.telegram_token:
            self.send_telegram(
                f"Compra de pociones completada.\nVentana: {display_title}\n"
                f"Maná: {bought_mana}/{mana_clicks}"
            )
        return True

    def send_telegram(self, message: str) -> None:
        if not self.telegram_token or not self.chat_id:
            return

        def _send() -> None:
            try:
                import requests

                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                requests.post(
                    url,
                    data={"chat_id": self.chat_id, "text": message},
                    timeout=10,
                )
            except Exception as e:
                write_log(f"send_telegram: {e}", "WARNING")

        threading.Thread(target=_send, daemon=True).start()

    def _send_request_auto_command(self, hwnd: int, display_title: str) -> bool:
        try:
            self.focus_window(hwnd)
            time.sleep(0.05)
            if not send_return_key(hwnd):
                return False
            time.sleep(0.12)
            type_chat_command("/request auto", interval=0.02)
            time.sleep(0.08)
            if not send_return_key(hwnd):
                return False
            self.print_signal.emit(f"{display_title} — comando /request auto enviado", QColor(137, 180, 250))
            return True
        except Exception as e:
            write_log(f"_send_request_auto_command: {e}", "WARNING")
            return False

    def _poll_telegram_commands(self, windows: list[tuple[int, int]]) -> None:
        if not self.telegram_token or not self.chat_id:
            return
        try:
            import requests

            offset = self._telegram_update_offset + 1 if self._telegram_update_offset else None
            params: dict[str, Any] = {"timeout": 1, "limit": 20}
            if offset is not None:
                params["offset"] = offset
            url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                return
            data = r.json() or {}
            results = data.get("result") or []
            for upd in results:
                try:
                    uid = int(upd.get("update_id", 0))
                    if uid > self._telegram_update_offset:
                        self._telegram_update_offset = uid
                    msg = upd.get("message") or {}
                    text = str(msg.get("text") or "").strip().lower()
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if not text.startswith("/request auto"):
                        continue
                    if chat_id and self.chat_id and chat_id != str(self.chat_id):
                        continue
                    self._handle_request_auto(text, windows)
                except Exception:
                    continue
        except Exception as e:
            write_log(f"_poll_telegram_commands: {e}", "WARNING")

    def _handle_request_auto(self, text: str, windows: list[tuple[int, int]]) -> None:
        if not windows:
            return
        idx = 1
        m = re.search(r"ventana\s*(\d+)", text)
        if m:
            idx = max(1, int(m.group(1)))
        target_hwnd: int | None = None
        target_win_index: int | None = None
        for hwnd, win_index in windows:
            if win_index == idx:
                target_hwnd = hwnd
                target_win_index = win_index
                break
        if target_hwnd is None:
            target_hwnd, target_win_index = windows[0]
        title = win32gui.GetWindowText(target_hwnd)
        display_title = f"[Ventana {target_win_index}] {title}"
        ok = self._send_request_auto_command(target_hwnd, display_title)
        if ok and self.telegram_enabled and self.telegram_token:
            self.send_telegram(f"/request auto enviado en {display_title}")

    def find_items(
        self,
        hwnd: int,
        region_rel: tuple[int, int, int, int],
        include_jewels: bool = True,
    ) -> list[tuple[str, tuple[int, int, int, int]]]:
        img = self.capture_region(hwnd, region_rel)
        if img is None:
            return []
        rect = win32gui.GetWindowRect(hwnd)
        win_left, win_top = rect[0], rect[1]
        found: list[tuple[str, tuple[int, int, int, int]]] = []
        h_img, w_img = img.shape[:2]
        search_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        for name, template in self.item_templates.items():
            if name in SKIP_IN_FIND_ITEMS:
                continue
            if not include_jewels and name in JEWELS:
                continue
            try:
                th, tw = template.shape[:2]
                if th > h_img or tw > w_img:
                    continue
                if len(template.shape) == 2:
                    search = search_gray
                    tmpl = template
                else:
                    search = img
                    tmpl = template
                result = cv2.matchTemplate(search, tmpl, cv2.TM_CCOEFF_NORMED)
                _min_v, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
                if max_val >= CONFIDENCE:
                    ml, mt = max_loc
                    left_screen = win_left + region_rel[0] + ml
                    top_screen = win_top + region_rel[1] + mt
                    base = os.path.splitext(os.path.basename(name))[0]
                    found.append((base, (left_screen, top_screen, tw, th)))
            except Exception as e:
                write_log(f"find_items {name}: {e}", "WARNING")
        return found

    def count_jewel_occurrences(self, jewel_file: str, region_abs: tuple[int, int, int, int]) -> int:
        template = self.item_templates.get(jewel_file)
        if template is None or self._sct is None:
            return 0
        left, top, width, height = region_abs
        try:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = np.array(self._sct.grab(monitor))
        except Exception as e:
            write_log(f"count_jewel_occurrences grab: {e}", "WARNING")
            return 0
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= JEWEL_CONFIDENCE)
        points = list(zip(*locations[::-1]))
        if not points:
            return 0
        min_dist = 15
        clusters: list[list[tuple[int, int]]] = []
        for pt in points:
            placed = False
            for cluster in clusters:
                if any(abs(pt[0] - c[0]) < min_dist and abs(pt[1] - c[1]) < min_dist for c in cluster):
                    cluster.append(pt)
                    placed = True
                    break
            if not placed:
                clusters.append([pt])
        return len(clusters)

    def pack_jewel(self, hwnd: int, jewel_name: str) -> bool:
        try:
            if not send_return_key(hwnd):
                return False
            time.sleep(0.15)
            foreground = win32gui.GetForegroundWindow()
            if foreground != hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.05)
            command = f"/pack {jewel_name} 10"
            type_chat_command(command, interval=0.02)
            time.sleep(0.1)
            if foreground and foreground != hwnd:
                win32gui.SetForegroundWindow(foreground)
            if not send_return_key(hwnd):
                return False
            time.sleep(1.0)
            return True
        except Exception as e:
            write_log(f"pack_jewel: {e}", "WARNING")
            return False

    def _extract_single_number_from_image(self, img_bgr: np.ndarray, hint: int | None = None) -> int | None:
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            # Fondo blanco, letras negras.
            _ok, th = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            _ok, th_otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            candidates: list[int] = []
            reader = _ensure_easyocr_reader()
            if reader is not None:
                for img in (th, th_otsu_inv):
                    # EasyOCR como motor principal para coordenadas.
                    results = reader.readtext(img, detail=1, paragraph=False, allowlist="0123456789")
                    for _bbox, text, conf in results:
                        if float(conf) < 0.20:
                            continue
                        nums = re.findall(r"\d{1,3}", str(text))
                        for n in nums:
                            val = int(n)
                            if 0 <= val <= 255:
                                candidates.append(val)
                                # Corrige falsos prefijos "1" (ej: 120 cuando era 20) según hint del tramo.
                                if (
                                    hint is not None
                                    and val >= 100
                                    and abs(val - hint) > 20
                                    and abs((val - 100) - hint) <= 8
                                ):
                                    candidates.append(val - 100)
                if candidates:
                    counts: dict[int, int] = {}
                    for v in candidates:
                        counts[v] = counts.get(v, 0) + 1
                    if hint is None:
                        return max(counts.keys(), key=lambda v: counts[v])
                    return max(counts.keys(), key=lambda v: (counts[v], -abs(v - hint)))
            return None
        except Exception as e:
            write_log(f"_extract_single_number_from_image: {e}", "WARNING")
            return None

    def get_current_map_coords(self, hwnd: int) -> tuple[int, int] | None:
        prev_hint = self._last_known_coords.get(hwnd)
        hx = prev_hint[0] if prev_hint is not None else None
        hy = prev_hint[1] if prev_hint is not None else None
        img_a = self.capture_region(hwnd, COORD_SCAN_REGION_A)
        img_b = self.capture_region(hwnd, COORD_SCAN_REGION_B)
        if img_a is None or img_b is None:
            return None
        x = self._extract_single_number_from_image(img_a, hint=hx)
        y = self._extract_single_number_from_image(img_b, hint=hy)
        if x is None or y is None:
            # Reintento único por tramo.
            img_a2 = self.capture_region(hwnd, COORD_SCAN_REGION_A)
            img_b2 = self.capture_region(hwnd, COORD_SCAN_REGION_B)
            if img_a2 is None or img_b2 is None:
                return None
            x = self._extract_single_number_from_image(img_a2, hint=hx)
            y = self._extract_single_number_from_image(img_b2, hint=hy)
            if x is None or y is None:
                self._show_ocr_debug(hwnd, img_a2, img_b2, None, None)
                return None
            self._show_ocr_debug(hwnd, img_a2, img_b2, x, y)
        else:
            self._show_ocr_debug(hwnd, img_a, img_b, x, y)
        self.print_signal.emit(
            f"OCR Easy A={x} B={y}",
            QColor(150, 150, 150),
        )
        return (x, y)

    def _show_ocr_debug(
        self,
        hwnd: int,
        img_a: np.ndarray,
        img_b: np.ndarray,
        x: int | None,
        y: int | None,
    ) -> None:
        if not self._ocr_debug_enabled:
            return
        try:
            def _prep(img: np.ndarray) -> np.ndarray:
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                g = cv2.resize(g, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
                g = cv2.GaussianBlur(g, (3, 3), 0)
                _ok, th = cv2.threshold(g, 150, 255, cv2.THRESH_BINARY_INV)
                return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)

            pa = _prep(img_a)
            pb = _prep(img_b)
            h = max(pa.shape[0], pb.shape[0])
            if pa.shape[0] != h:
                pa = cv2.resize(pa, (pa.shape[1], h))
            if pb.shape[0] != h:
                pb = cv2.resize(pb, (pb.shape[1], h))
            gap = np.full((h, 10, 3), 20, dtype=np.uint8)
            canvas = np.hstack([pa, gap, pb])
            label = f"A={x if x is not None else '-'}  B={y if y is not None else '-'}"
            cv2.putText(canvas, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(canvas, f"hwnd={hwnd}", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.imshow("OCR Coords Debug", canvas)
            cv2.waitKey(1)
        except Exception as e:
            self._ocr_debug_enabled = False
            write_log(f"ocr debug window: {e}", "WARNING")

    def _click_move_direction(self, hwnd: int, direction: str, offset: int | None = None) -> None:
        rect = win32gui.GetWindowRect(hwnd)
        cx = rect[0] + CHAR_CENTER_RELATIVE[0]
        cy = rect[1] + CHAR_CENTER_RELATIVE[1]
        step = MOVE_CLICK_OFFSET if offset is None else int(offset)
        dx, dy = 0, 0
        if direction == "right":
            dx = step
        elif direction == "left":
            dx = -step
        elif direction == "up":
            dy = -step
        elif direction == "up_right":
            dx = step
            dy = -step
        elif direction == "up_left":
            dx = -step
            dy = -step
        elif direction == "down_right":
            dx = step
            dy = step
        elif direction == "down_left":
            dx = -step
            dy = step
        else:
            dy = step
        click_at(cx + dx, cy + dy)

    def _unstuck_with_long_clicks(
        self,
        hwnd: int,
        display_title: str,
        current: tuple[int, int],
        target: tuple[int, int],
    ) -> None:
        """Primer nivel anti-atasco: clicks más lejos del centro. No reinicia el retorno al spot."""
        direction = self._choose_move_direction(current, target) or self._last_move_direction.get(hwnd, "right")
        self._last_move_direction[hwnd] = direction
        self.print_signal.emit(
            f"{display_title} — atascado, desbloqueo con clicks largos ({direction})",
            QColor(250, 179, 135),
        )
        self._click_move_direction(hwnd, direction, offset=MOVE_UNSTUCK_OFFSET)
        time.sleep(0.12)
        self._click_move_direction(hwnd, direction, offset=MOVE_UNSTUCK_OFFSET)
        self._stuck_since[hwnd] = time.time()

    def _choose_move_direction(self, current: tuple[int, int], target: tuple[int, int]) -> str | None:
        cx, cy = current
        tx, ty = target
        if (cx, cy) == (tx, ty):
            return None
        current_u = cx + cy
        target_u = tx + ty
        current_v = cx - cy
        target_v = tx - ty
        du = target_u - current_u
        dv = target_v - current_v
        if abs(du) >= abs(dv):
            return "right" if du > 0 else "left"
        return "down" if dv > 0 else "up"

    def _choose_move_direction_direct(self, current: tuple[int, int], target: tuple[int, int]) -> str | None:
        """
        Dirección directa por delta de coordenadas (usada para trayectos cortos de compra).
        En este cliente: Y mayor implica click hacia arriba en pantalla.
        """
        cx, cy = current
        tx, ty = target
        dx = tx - cx
        dy = ty - cy
        if abs(dx) <= 1 and abs(dy) <= 1:
            return None
        if abs(dx) >= 2 and abs(dy) >= 2:
            if dx > 0 and dy > 0:
                return "up_right"
            if dx > 0 and dy < 0:
                return "down_right"
            if dx < 0 and dy > 0:
                return "up_left"
            return "down_left"
        if abs(dx) >= abs(dy):
            return "right" if dx > 0 else "left"
        return "up" if dy > 0 else "down"

    def _should_log_ocr_no_read(self, hwnd: int, min_interval_sec: float = 1.5) -> bool:
        now = time.monotonic()
        last = float(self._last_ocr_no_read_log_mono.get(hwnd, 0.0))
        if (now - last) < min_interval_sec:
            return False
        self._last_ocr_no_read_log_mono[hwnd] = now
        return True

    def _is_opposite_direction(self, d1: str, d2: str) -> bool:
        opposite = {
            "right": "left",
            "left": "right",
            "up": "down",
            "down": "up",
            "up_right": "down_left",
            "down_left": "up_right",
            "up_left": "down_right",
            "down_right": "up_left",
        }
        return opposite.get(d1) == d2

    def _apply_direction_inversion(self, hwnd: int, direction: str) -> str:
        inv = self._direction_inversion.get(hwnd) or {"h": False, "v": False}
        d = direction
        if inv.get("h", False):
            hswap = {
                "left": "right",
                "right": "left",
                "up_left": "up_right",
                "up_right": "up_left",
                "down_left": "down_right",
                "down_right": "down_left",
            }
            d = hswap.get(d, d)
        if inv.get("v", False):
            vswap = {
                "up": "down",
                "down": "up",
                "up_left": "down_left",
                "down_left": "up_left",
                "up_right": "down_right",
                "down_right": "up_right",
            }
            d = vswap.get(d, d)
        return d

    def _register_move_feedback(self, hwnd: int, current: tuple[int, int], target: tuple[int, int], direction: str) -> None:
        self._move_feedback[hwnd] = {
            "dist": abs(target[0] - current[0]) + abs(target[1] - current[1]),
            "direction": direction,
        }

    def _adjust_direction_from_feedback(self, hwnd: int, current: tuple[int, int], target: tuple[int, int], display_title: str) -> None:
        fb = self._move_feedback.get(hwnd)
        if not fb:
            return
        prev_dist = float(fb.get("dist", 0.0))
        direction = str(fb.get("direction") or "")
        now_dist = abs(target[0] - current[0]) + abs(target[1] - current[1])
        self._move_feedback.pop(hwnd, None)
        if now_dist <= (prev_dist + 1.0):
            return
        inv = self._direction_inversion.setdefault(hwnd, {"h": False, "v": False})
        if direction in {"up_left", "up_right", "down_left", "down_right"}:
            inv["h"] = not bool(inv.get("h", False))
            inv["v"] = not bool(inv.get("v", False))
            self.print_signal.emit(
                f"{display_title} — autocorrección: invirtiendo ejes horizontal y vertical",
                QColor(250, 179, 135),
            )
        elif direction in {"left", "right"}:
            inv["h"] = not bool(inv.get("h", False))
            self.print_signal.emit(
                f"{display_title} — autocorrección: invirtiendo eje horizontal",
                QColor(250, 179, 135),
            )
        elif direction in {"up", "down"}:
            inv["v"] = not bool(inv.get("v", False))
            self.print_signal.emit(
                f"{display_title} — autocorrección: invirtiendo eje vertical",
                QColor(250, 179, 135),
            )

    def _stabilize_direction(
        self,
        hwnd: int,
        proposed: str,
        current: tuple[int, int],
        target: tuple[int, int],
    ) -> str:
        """Evita oscilación rápida de ida/vuelta por ruido de lectura."""
        previous = self._last_move_direction.get(hwnd)
        if not previous or previous == proposed:
            return proposed
        if not self._is_opposite_direction(previous, proposed):
            return proposed

        now = time.monotonic()
        last_change = float(self._last_direction_change_mono.get(hwnd, 0.0))
        dist = abs(target[0] - current[0]) + abs(target[1] - current[1])
        # Si intenta invertir demasiado rápido y aún estamos lejos del spot, mantener rumbo anterior.
        if (now - last_change) < 0.9 and dist > (SPOT_COORD_TOLERANCE * 3):
            return previous
        return proposed

    def _detour_from_direction(self, hwnd: int, base: str) -> str:
        toggle = self._detour_turn_toggle.get(hwnd, False)
        self._detour_turn_toggle[hwnd] = not toggle
        if base == "right":
            return "up_right" if toggle else "down_right"
        if base == "left":
            return "up_left" if toggle else "down_left"
        if base == "up":
            return "up_left" if toggle else "up_right"
        if base == "down":
            return "down_left" if toggle else "down_right"
        return "down_right" if toggle else "up_right"

    def _find_red_arrow_center(self, img_bgr: np.ndarray) -> tuple[int, int] | None:
        try:
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            m1 = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
            m2 = cv2.inRange(hsv, (168, 80, 80), (180, 255, 255))
            m = cv2.bitwise_or(m1, m2)
            contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            best = max(contours, key=cv2.contourArea)
            if cv2.contourArea(best) < 8:
                return None
            m = cv2.moments(best)
            if m["m00"] <= 0:
                return None
            return int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
        except Exception:
            return None

    def _direction_to_vec(self, direction: str) -> tuple[float, float]:
        dirs = {
            "right": (1.0, 0.0),
            "left": (-1.0, 0.0),
            "up": (0.0, -1.0),
            "down": (0.0, 1.0),
            "up_right": (0.707, -0.707),
            "up_left": (-0.707, -0.707),
            "down_right": (0.707, 0.707),
            "down_left": (-0.707, 0.707),
        }
        return dirs.get(direction, (0.0, 1.0))

    def _direction_candidates(self, base: str) -> list[str]:
        if base == "right":
            return ["right", "up_right", "down_right", "up", "down", "left"]
        if base == "left":
            return ["left", "up_left", "down_left", "up", "down", "right"]
        if base == "up":
            return ["up", "up_left", "up_right", "left", "right", "down"]
        if base == "down":
            return ["down", "down_left", "down_right", "left", "right", "up"]
        return [base, "right", "left", "up", "down"]

    def _walkable_reference_hsv(self, hsv: np.ndarray, center: tuple[int, int]) -> np.ndarray:
        h, w = hsv.shape[:2]
        cx, cy = center
        x0, x1 = max(0, cx - 6), min(w, cx + 7)
        y0, y1 = max(0, cy - 6), min(h, cy + 7)
        patch = hsv[y0:y1, x0:x1]
        if patch.size == 0:
            return np.array([90.0, 80.0, 140.0], dtype=np.float32)
        # Excluir rojos (triángulo) para no contaminar referencia de terreno caminable.
        hch = patch[:, :, 0].astype(np.float32)
        sch = patch[:, :, 1].astype(np.float32)
        red_mask = ((hch <= 12) | (hch >= 168)) & (sch >= 90)
        sel = patch[~red_mask]
        if sel.size == 0:
            sel = patch.reshape(-1, 3)
        return np.median(sel.reshape(-1, 3).astype(np.float32), axis=0)

    def _sample_line(self, p0: tuple[float, float], p1: tuple[float, float], n: int = 22) -> list[tuple[int, int]]:
        pts: list[tuple[int, int]] = []
        for i in range(n):
            t = i / float(max(1, n - 1))
            x = int(p0[0] * (1 - t) + p1[0] * t)
            y = int(p0[1] * (1 - t) + p1[1] * t)
            pts.append((x, y))
        return pts

    def _score_direction_candidate(
        self,
        gray: np.ndarray,
        hsv: np.ndarray,
        red: tuple[int, int],
        target_px: tuple[float, float],
        direction: str,
        terrain_ref_hsv: np.ndarray,
    ) -> tuple[float, float, float, float]:
        h, w = gray.shape[:2]
        vx, vy = self._direction_to_vec(direction)
        probe_len = 96.0
        end = (
            max(0.0, min(w - 1.0, red[0] + vx * probe_len)),
            max(0.0, min(h - 1.0, red[1] + vy * probe_len)),
        )
        pts = self._sample_line((float(red[0]), float(red[1])), end, n=22)
        vals_gray: list[float] = []
        vals_hsv: list[np.ndarray] = []
        for x, y in pts:
            if 0 <= x < w and 0 <= y < h:
                vals_gray.append(float(gray[y, x]))
                vals_hsv.append(hsv[y, x].astype(np.float32))
        if not vals_gray:
            return -99.0, 1.0, 1.0, -1.0
        dark_frac = float(np.mean(np.array(vals_gray, dtype=np.float32) < OBSTACLE_DARK_THRESHOLD))
        line_hsv = np.mean(np.stack(vals_hsv, axis=0), axis=0)
        # Distancia de color circular en H + lineal en S/V (normalizada aprox).
        dh = abs(float(line_hsv[0] - terrain_ref_hsv[0]))
        dh = min(dh, 180.0 - dh) / 90.0
        ds = abs(float(line_hsv[1] - terrain_ref_hsv[1])) / 255.0
        dv = abs(float(line_hsv[2] - terrain_ref_hsv[2])) / 255.0
        color_penalty = (0.7 * dh) + (0.2 * ds) + (0.1 * dv)

        gx = float(target_px[0] - red[0])
        gy = float(target_px[1] - red[1])
        gn = math.hypot(gx, gy) or 1.0
        cn = math.hypot(vx, vy) or 1.0
        progress = (vx * gx + vy * gy) / (cn * gn)  # [-1, 1]

        score = (1.65 * progress) - (1.35 * dark_frac) - (0.95 * color_penalty)
        return score, dark_frac, color_penalty, progress

    def _reset_ocr_state_for_window(self, hwnd: int) -> None:
        """Limpia caches/estado OCR para evitar arrastre entre mapas."""
        self._last_known_coords.pop(hwnd, None)
        self._coord_history.pop(hwnd, None)
        self._ocr_bootstrap_reads.pop(hwnd, None)
        self._ocr_no_read_count.pop(hwnd, None)
        self._stuck_since.pop(hwnd, None)
        self._last_move_direction.pop(hwnd, None)
        self._move_feedback.pop(hwnd, None)
        self._direction_inversion.pop(hwnd, None)
        self._last_ocr_no_read_log_mono.pop(hwnd, None)

    def _teleport_via_special_route(
        self,
        hwnd: int,
        display_title: str,
        target_map: str,
        route: dict,
    ) -> bool:
        """Teleport en dos pasos: gateway por M + caminata por portal manual.

        Soporta dos formatos de ruta:
        - `post_walk_steps`: lista de direcciones (ej. ["left", "down"]).
        - `post_walk_direction` + `post_walk_clicks`: una sola dirección repetida N veces.
        """
        gateway = str(route.get("gateway_map", "")).strip()
        if not gateway:
            return False
        steps_cfg = route.get("post_walk_steps")
        if steps_cfg:
            steps: list[str] = [str(d) for d in steps_cfg]
        else:
            direction = str(route.get("post_walk_direction", "down"))
            clicks = int(route.get("post_walk_clicks", 1) or 0)
            steps = [direction] * max(clicks, 1)
        click_delay = float(route.get("post_walk_click_delay", 0.9))
        settle = float(route.get("post_walk_settle", 2.5))

        steps_label = " → ".join(steps) if steps else "sin pasos"
        self.print_signal.emit(
            f"{display_title} — ruta especial a {target_map}: vía {gateway} ({steps_label})",
            QColor(137, 180, 250),
        )
        if self.is_minimap_open(hwnd):
            self.ensure_minimap_closed(hwnd, display_title)
        if not self.teleport_to_map(hwnd, display_title, gateway):
            self.print_signal.emit(
                f"{display_title} — no se pudo teletransportar al gateway {gateway}",
                QColor(243, 139, 168),
            )
            return False
        if self.is_minimap_open(hwnd):
            self.ensure_minimap_closed(hwnd, display_title)
        for i, direction in enumerate(steps, start=1):
            self._click_move_direction(hwnd, direction)
            self.print_signal.emit(
                f"{display_title} — caminando hacia portal {i}/{len(steps)} ({direction})",
                QColor(148, 226, 213),
            )
            time.sleep(click_delay)
        time.sleep(settle)
        self._reset_ocr_state_for_window(hwnd)
        return True

    def teleport_to_map(self, hwnd: int, display_title: str, map_name: str) -> bool:
        """Abre M, elige mapa por plantilla y confirma el TP.

        Solo Icarius2 usa `SPECIAL_MAP_ROUTES`: M → Icarius y luego los pasos al portal.
        Exile y el resto: un solo TP por M; el desplazamiento al spot lo hace `navigate_to_coords_by_ocr`.
        """
        name = map_name.strip()
        if not name:
            return True
        special = SPECIAL_MAP_ROUTES.get(name)
        # Solo se usa la ruta especial si define un mapa "gateway".
        if special is not None and str(special.get("gateway_map", "")).strip():
            return self._teleport_via_special_route(hwnd, display_title, name, special)
        # Si el popup "outside city" sigue visible bloquearía la lista de mapas: ciérralo primero.
        if self.is_city_popup_present(hwnd):
            self.print_signal.emit(
                f"{display_title} — popup de ciudad presente antes de abrir M, cerrando primero",
                QColor(250, 179, 135),
            )
            if not self.dismiss_city_popup(hwnd, display_title):
                return False
        tpl_name = map_template_filename(name)
        tpl = self.item_templates.get(tpl_name)
        if tpl is None:
            self.print_signal.emit(
                f"{display_title} — plantilla de mapa no cargada: {tpl_name}",
                QColor(243, 139, 168),
            )
            return False
        # Reset OCR al iniciar salto de mapa (tecla M).
        self._reset_ocr_state_for_window(hwnd)
        send_m_key(hwnd)
        time.sleep(0.45)
        img = self.capture_region(hwnd, MAP_LIST_REGION)
        if img is None:
            return False
        th, tw = tpl.shape[:2]
        ih, iw = img.shape[:2]
        if th > ih or tw > iw:
            self.print_signal.emit(f"{display_title} — región de mapas demasiado pequeña", QColor(243, 139, 168))
            return False
        if len(tpl.shape) == 2:
            search = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            use_t = tpl
        else:
            search = img
            use_t = tpl
        res = cv2.matchTemplate(search, use_t, cv2.TM_CCOEFF_NORMED)
        _min_v, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < MAP_SELECTION_THRESHOLD:
            self.print_signal.emit(
                f"{display_title} — mapa '{name}' no encontrado en lista (sim {max_val:.2f})",
                QColor(243, 139, 168),
            )
            return False
        ml, mt = max_loc
        rect = win32gui.GetWindowRect(hwnd)
        abs_x = rect[0] + MAP_LIST_REGION[0] + ml + tw // 2
        abs_y = rect[1] + MAP_LIST_REGION[1] + mt + th // 2
        click_at(abs_x, abs_y)
        self.print_signal.emit(
            f"{display_title} — teletransporte a {name} (sim {max_val:.2f})",
            QColor(137, 180, 250),
        )
        # Reset adicional post-teleport para garantizar estado limpio.
        self._reset_ocr_state_for_window(hwnd)
        time.sleep(WAIT_AFTER_TELEPORT)
        return True

    def navigate_to_spot_with_tab(
        self,
        hwnd: int,
        display_title: str,
        target_coords: tuple[int, int],
        respawn_map_name: str,
    ) -> bool:
        """Compatibilidad con llamadas antiguas: navegación solo por OCR (minimapa cerrado)."""
        if self.is_minimap_open(hwnd):
            self.ensure_minimap_closed(hwnd, display_title)
        reached, _retry = self.navigate_to_coords_by_ocr(
            hwnd,
            display_title,
            target_coords,
            enable_stall_restart=False,
            log_prefix="OCR compra",
        )
        return reached

    def navigate_to_coords_by_ocr(
        self,
        hwnd: int,
        display_title: str,
        target_coords: tuple[int, int],
        *,
        enable_stall_restart: bool = False,
        stall_same_coord_sec: float | None = None,
        log_prefix: str = "OCR compra",
    ) -> tuple[bool, bool]:
        """Navega por OCR de coordenadas.

        Anti-atascos (solo retorno al spot activa el reinicio fuerte):
        - Cada `RETURN_UNSTUCK_LONG_CLICK_AFTER_SEC` sin cambio de coords: clicks largos
          (`_unstuck_with_long_clicks`), para intentar salir sin reiniciar.
        - Si con `enable_stall_restart` las coords siguen iguales durante `stall_same_coord_sec`
          (p. ej. 20 s) pese a lo anterior, se pide reiniciar todo el flujo "volver al spot".
        """
        if stall_same_coord_sec is None:
            stall_same_coord_sec = float(SPOT_RETURN_STALL_RESTART_SEC)
        stall_anchor: tuple[int, int] | None = None
        stall_mono: float | None = None
        while self._running:
            current = self.get_current_map_coords(hwnd)
            if current is None:
                if enable_stall_restart:
                    stall_anchor, stall_mono = None, None
                self._ocr_no_read_count[hwnd] = self._ocr_no_read_count.get(hwnd, 0) + 1
                no_read_count = self._ocr_no_read_count[hwnd]
                if self._should_log_ocr_no_read(hwnd):
                    self.print_signal.emit(
                        f"{display_title} — {log_prefix} sin lectura, esperando lectura estable",
                        QColor(243, 139, 168),
                    )
                if no_read_count % 20 == 0:
                    self.print_signal.emit(
                        f"{display_title} — {log_prefix} sin lectura prolongada ({no_read_count}), reiniciando estado OCR",
                        QColor(250, 179, 135),
                    )
                    self._reset_ocr_state_for_window(hwnd)
                    continue
                if no_read_count % 6 == 0:
                    direction = self._last_move_direction.get(hwnd, "right")
                    self._click_move_direction(hwnd, direction)
                time.sleep(MOVE_STEP_PAUSE + 0.12)
                continue
            else:
                self._ocr_no_read_count[hwnd] = 0
                prev = self._last_known_coords.get(hwnd)
                if prev is not None and prev == current:
                    self._stuck_since.setdefault(hwnd, time.time())
                else:
                    self._stuck_since.pop(hwnd, None)
                self._last_known_coords[hwnd] = current

            if enable_stall_restart:
                if stall_anchor is not None and stall_anchor == current:
                    if stall_mono is None:
                        stall_mono = time.monotonic()
                    elif (time.monotonic() - stall_mono) >= stall_same_coord_sec:
                        return False, True
                else:
                    stall_anchor = current
                    stall_mono = None

            if self._is_spot_reached(current, target_coords):
                self._stuck_since.pop(hwnd, None)
                self.print_signal.emit(
                    f"{display_title} — {log_prefix} llegó al objetivo ({current[0]},{current[1]})",
                    QColor(166, 227, 161),
                )
                return True, False

            direction = self._choose_move_direction_direct(current, target_coords)
            if direction is None:
                return True, False
            dx = target_coords[0] - current[0]
            dy = target_coords[1] - current[1]
            self.print_signal.emit(
                f"{display_title} — {log_prefix} actual={current[0]},{current[1]} "
                f"objetivo={target_coords[0]},{target_coords[1]} dx={dx} dy={dy} dir={direction}",
                QColor(150, 150, 150),
            )
            self._last_move_direction[hwnd] = direction
            self._click_move_direction(hwnd, direction)
            time.sleep(MOVE_STEP_PAUSE)

            stuck_from = self._stuck_since.get(hwnd)
            if stuck_from is not None and (time.time() - stuck_from) >= RETURN_UNSTUCK_LONG_CLICK_AFTER_SEC:
                self._unstuck_with_long_clicks(hwnd, display_title, current, target_coords)
                time.sleep(MOVE_STEP_PAUSE)
        return False, False

    def handle_return_to_spot(
        self,
        hwnd: int,
        display_title: str,
        target_coords: tuple[int, int] | None,
        respawn_map_name: str,
    ) -> bool:
        if target_coords is None:
            return True
        while self._running:
            if self.pk_mode_enabled and not self.pk_sent_for_recovery.get(hwnd, False):
                if send_pk_toggle(hwnd, repeats=3):
                    self.print_signal.emit(f"{display_title} — PK activado (Ctrl x3)", QColor(137, 180, 250))
                self.pk_sent_for_recovery[hwnd] = True
                time.sleep(0.15)
            if respawn_map_name and self._death_teleport_done.get(hwnd) is False:
                _ok_tp = self.teleport_to_map(hwnd, display_title, respawn_map_name)
                self._death_teleport_done[hwnd] = True

            if self.is_minimap_open(hwnd):
                self.ensure_minimap_closed(hwnd, display_title)

            reached, retry_full = self.navigate_to_coords_by_ocr(
                hwnd,
                display_title,
                target_coords,
                enable_stall_restart=True,
                stall_same_coord_sec=float(SPOT_RETURN_STALL_RESTART_SEC),
                log_prefix="OCR spot",
            )
            if reached:
                if self.is_minimap_open(hwnd):
                    self.ensure_minimap_closed(hwnd, display_title)
                send_home_key(hwnd)
                self.print_signal.emit(f"{display_title} — spot alcanzado, HOME enviado", QColor(166, 227, 161))
                return True
            if retry_full:
                self.print_signal.emit(
                    f"{display_title} — anti-atasco (clicks largos) sin éxito: mismas coords OCR "
                    f">{int(SPOT_RETURN_STALL_RESTART_SEC)}s; reiniciando 'volver al spot' desde el inicio",
                    QColor(250, 179, 135),
                )
                self._death_teleport_done[hwnd] = False
                self.return_steps[hwnd] = 0
                self._reset_ocr_state_for_window(hwnd)
                self._last_known_coords.pop(hwnd, None)
                self._stuck_since.pop(hwnd, None)
                self._ocr_no_read_count[hwnd] = 0
                time.sleep(0.35)
                continue
            return False
        return False

    def _notify_return_cancelled(self, hwnd: int, display_title: str) -> None:
        self.print_signal.emit(
            f"{display_title} — retorno cancelado: límite de pasos ({MAX_RETURN_STEPS_PER_WINDOW})",
            QColor(243, 139, 168),
        )
        if self.telegram_enabled and self.telegram_token:
            self.send_telegram(
                f"No se alcanzó el spot tras {MAX_RETURN_STEPS_PER_WINDOW} pasos.\nVentana: {display_title}"
            )
