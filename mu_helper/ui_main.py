"""Ventana principal y consola (tema oscuro, layout tipo panel + pestañas)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import win32api
import win32gui
from PySide6.QtCore import QMetaObject, Qt, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from pynput import keyboard

from mu_helper import __version__
from mu_helper.config import BASE_DIR, RESPAWN_MAP_DISPLAY_NAMES, TELEGRAM_CONFIG_FILE, WINDOW_CONFIG_FILE
from mu_helper.game_thread import MainThread
from mu_helper.healer_thread import HealerThread
from mu_helper.license import check_license, get_license_days_left, license_status_color_days
from mu_helper.ui_dialogs import LicenseDialog, TelegramSetupWizard
from mu_helper.window_finder import get_game_windows

_CONS = QFont("Consolas", 10)
_TS_MUTED = QColor(108, 112, 134)
_DEFAULT_LOG = QColor(205, 214, 244)


def _qcolor_from_hex(hex_color: str) -> QColor:
    c = QColor(hex_color)
    return c if c.isValid() else _DEFAULT_LOG


class Console(QTextEdit):
    MAX_LINES = 500

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setFont(_CONS)
        self.setPlaceholderText("Los eventos del helper aparecerán aquí…")
        self._line_count = 0

    def print_message(self, msg: str, color: QColor) -> None:
        while self._line_count >= self.MAX_LINES:
            cur = self.textCursor()
            cur.movePosition(QTextCursor.Start)
            cur.select(QTextCursor.LineUnderCursor)
            cur.removeSelectedText()
            cur.deleteChar()
            self._line_count -= 1

        ts = datetime.now().strftime("%H:%M:%S")
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        self.setTextCursor(cur)
        self.setTextColor(_TS_MUTED)
        self.insertPlainText(f"[{ts}] ")
        self.setTextColor(color if color.isValid() else _DEFAULT_LOG)
        self.insertPlainText(msg + "\n")
        self._line_count += 1
        self.setTextColor(_DEFAULT_LOG)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self) -> None:
        self.clear()
        self._line_count = 0


class MainWindow(QMainWindow):
    def __init__(self, item_templates: dict[str, Any]) -> None:
        super().__init__()
        self.item_templates = item_templates
        self.setWindowTitle(f"Ultimate Mu Helper by Tyferiusk · v{__version__}")
        self.setMinimumSize(560, 860)
        self.resize(560, 860)
        _ico = BASE_DIR / "mu_cleaner.ico"
        if _ico.is_file():
            self.setWindowIcon(QIcon(str(_ico)))

        if not check_license():
            dlg = LicenseDialog(self)
            if not dlg.exec():
                sys.exit(0)

        self.thread: MainThread | None = None
        self.healer_thread: HealerThread | None = None
        self._healer_active = False
        self.listener: keyboard.GlobalHotKeys | None = None

        self.window_config_path = Path(BASE_DIR) / WINDOW_CONFIG_FILE
        self.window_configs: dict[str, dict[str, Any]] = self._load_window_configs()

        self.scanning = False
        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self._update_scanning_dots)
        self.dot_count = 0

        self._setup_ui()
        self._refresh_window_selector()
        self._show_system_info()

        self.listener = keyboard.GlobalHotKeys(
            {
                "<f4>": self.toggle_script,
                "<end>": self.toggle_healer,
            }
        )
        self.listener.start()

        self.startTimer(1000)

    def _load_window_configs(self) -> dict[str, dict[str, Any]]:
        if not self.window_config_path.is_file():
            return {}
        try:
            obj = json.loads(self.window_config_path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _save_window_configs(self) -> None:
        self.window_config_path.write_text(
            json.dumps(self.window_configs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        top = QVBoxLayout()
        title = QLabel("Ultimate Mu Helper")
        title.setObjectName("appTitle")
        top.addWidget(title)
        sub = QLabel("Mu Online · F4 helper · Fin auto poción")
        sub.setObjectName("appSubtitle")
        top.addWidget(sub)
        root.addLayout(top)

        root.addWidget(self._build_status_bar())

        tabs = QTabWidget()
        tabs.addTab(self._build_control_tab(), "Control")
        tabs.addTab(self._build_healer_tab(), "Healer")
        tabs.addTab(self._build_log_tab(), "Actividad")
        root.addWidget(tabs, stretch=1)

        root.addWidget(self._build_button_bar())

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("statusBarFrame")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        self.status_pill = QLabel("Detenido")
        self.status_pill.setStyleSheet("font-weight: 700; font-size: 13px; color: #bac2de;")
        lay.addWidget(self.status_pill)
        lay.addStretch(1)

        self.windows_label = QLabel("Ventanas: —")
        self.windows_label.setObjectName("windowsLabel")
        lay.addWidget(self.windows_label)

        v = QFrame()
        v.setObjectName("vLine")
        v.setFrameShape(QFrame.VLine)
        v.setFixedWidth(1)
        lay.addWidget(v)

        self.license_chip = QLabel("Licencia: —")
        self.license_chip.setObjectName("licenseChip")
        lay.addWidget(self.license_chip)

        return bar

    def _build_control_tab(self) -> QWidget:
        content = QWidget()
        v = QVBoxLayout(content)
        v.setSpacing(8)

        fg = QGroupBox("Funciones")
        gl = QGridLayout(fg)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(4)
        self.helper_check = QCheckBox("Auto Helper")
        self.cleaner_check = QCheckBox("Limpiar inventario")
        self.pack_check = QCheckBox("Pack de joyas")
        self.telegram_check = QCheckBox("Telegram")
        self.pk_mode_check = QCheckBox("PK al revivir (Ctrl x3)")
        self.telegram_check.toggled.connect(self._on_telegram_toggled)
        gl.addWidget(self.helper_check, 0, 0)
        gl.addWidget(self.cleaner_check, 0, 1)
        gl.addWidget(self.pack_check, 1, 0)
        gl.addWidget(self.telegram_check, 1, 1)
        gl.addWidget(self.pk_mode_check, 2, 0)
        v.addWidget(fg)

        rg = QGroupBox("Retorno por ventana")
        rl = QVBoxLayout(rg)
        rl.setSpacing(4)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Ventana:"))
        self.window_combo = QComboBox()
        self.window_combo.currentIndexChanged.connect(self._on_window_selected)
        self.refresh_windows_btn = QPushButton("Actualizar")
        self.refresh_windows_btn.setObjectName("ghost")
        self.refresh_windows_btn.clicked.connect(self._refresh_window_selector)
        self.identify_window_btn = QPushButton("Identificar")
        self.identify_window_btn.setObjectName("ghost")
        self.identify_window_btn.clicked.connect(self._identify_selected_window)
        sel_row.addWidget(self.window_combo, stretch=1)
        sel_row.addWidget(self.refresh_windows_btn)
        sel_row.addWidget(self.identify_window_btn)
        rl.addLayout(sel_row)

        self.window_return_check = QCheckBox("Volver al spot tras morir")
        rl.addWidget(self.window_return_check)

        char_row = QHBoxLayout()
        char_row.addWidget(QLabel("Nombre personaje:"))
        self.character_name_input = QLineEdit()
        self.character_name_input.setPlaceholderText("Ej: BK_Main")
        char_row.addWidget(self.character_name_input, stretch=1)
        rl.addLayout(char_row)

        coord_row = QHBoxLayout()
        self.coord_x_input = QLineEdit()
        self.coord_x_input.setPlaceholderText("X")
        self.coord_y_input = QLineEdit()
        self.coord_y_input.setPlaceholderText("Y")
        coord_row.addWidget(QLabel("Coordenadas:"))
        coord_row.addWidget(self.coord_x_input)
        coord_row.addWidget(self.coord_y_input)
        rl.addLayout(coord_row)

        map_row = QHBoxLayout()
        map_row.addWidget(QLabel("Mapa al teletransportarse:"))
        self.map_combo = QComboBox()
        self.map_combo.addItems(list(RESPAWN_MAP_DISPLAY_NAMES))
        map_row.addWidget(self.map_combo, stretch=1)
        rl.addLayout(map_row)

        buy_group = QGroupBox("Compra automática de pociones")
        buy_grid = QGridLayout(buy_group)
        buy_grid.setHorizontalSpacing(8)
        buy_grid.setVerticalSpacing(4)
        buy_hint = QLabel("Configuración independiente por ventana/personaje.")
        buy_hint.setObjectName("hintLabel")
        buy_grid.addWidget(buy_hint, 0, 0, 1, 4)
        self.auto_buy_potions_check = QCheckBox("Activar compra al quedarse sin maná")
        buy_grid.addWidget(self.auto_buy_potions_check, 1, 0, 1, 4)

        self.buy_mana_check = QCheckBox("Comprar pociones de maná")
        self.buy_mana_clicks_input = QLineEdit()
        self.buy_mana_clicks_input.setPlaceholderText("Clicks")
        self.buy_mana_clicks_input.setMaximumWidth(80)
        buy_grid.addWidget(self.buy_mana_check, 2, 0)
        buy_grid.addWidget(QLabel("Cantidad:"), 2, 1)
        buy_grid.addWidget(self.buy_mana_clicks_input, 2, 2)
        rl.addWidget(buy_group)

        save_row = QHBoxLayout()
        self.save_window_cfg_btn = QPushButton("Guardar configuración")
        self.save_window_cfg_btn.clicked.connect(self._save_current_window_config)
        save_row.addStretch(1)
        save_row.addWidget(self.save_window_cfg_btn)
        rl.addLayout(save_row)

        v.addWidget(rg)

        tg = QGroupBox("Telegram")
        th = QHBoxLayout(tg)
        th.setSpacing(6)
        self.config_telegram_btn = QPushButton("Configurar…")
        self.config_telegram_btn.setEnabled(False)
        self.config_telegram_btn.clicked.connect(self._open_telegram_wizard)
        self.tg_status = QLabel()
        self._refresh_telegram_badge()
        th.addWidget(self.config_telegram_btn)
        th.addWidget(self.tg_status)
        th.addStretch(1)
        v.addWidget(tg)

        hint = QLabel("Configura cada ventana y pulsa Guardar antes de iniciar.")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_healer_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        hg = QGroupBox("Auto poción")
        hl = QVBoxLayout(hg)
        hl.setSpacing(6)

        self.healer_status = QLabel("Desactivado")
        self.healer_status.setStyleSheet("font-weight: 700; font-size: 13px; color: #bac2de;")
        hl.addWidget(self.healer_status)

        desc = QLabel(
            "Alterna Q y W en serie (Q→W→Q→W…) de forma rápida sobre la ventana "
            "seleccionada en la pestaña Control.\n"
            "Tecla Fin: activar / desactivar (funciona con el helper detenido)."
        )
        desc.setObjectName("hintLabel")
        desc.setWordWrap(True)
        hl.addWidget(desc)
        v.addWidget(hg)
        v.addStretch(1)
        return w

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.console = Console()
        v.addWidget(self.console)
        clear_btn = QPushButton("Vaciar consola")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self.console.clear_log)
        v.addWidget(clear_btn)
        return w

    def _build_button_bar(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 0)
        h.setSpacing(8)
        self.start_btn = QPushButton("Iniciar")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("Detener")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        h.addWidget(self.start_btn, stretch=1)
        h.addWidget(self.stop_btn, stretch=1)
        self.start_btn.clicked.connect(self.start_thread)
        self.stop_btn.clicked.connect(self.stop_thread)
        return row

    def _window_key(self) -> str | None:
        hwnd = self.window_combo.currentData()
        if hwnd is None:
            return None
        return f"hwnd_{int(hwnd)}"

    def _refresh_window_selector(self) -> None:
        windows = get_game_windows()
        selected = self.window_combo.currentData()
        active_keys = {f"hwnd_{int(hwnd)}" for hwnd, _idx in windows}
        # Limpia configuraciones de ventanas que ya no existen (evita HWNDs stale).
        if active_keys:
            self.window_configs = {
                k: v for k, v in self.window_configs.items() if not k.startswith("hwnd_") or k in active_keys
            }
        self.window_combo.blockSignals(True)
        self.window_combo.clear()
        if not windows:
            self.window_combo.addItem("Sin ventanas detectadas", None)
        else:
            for hwnd, idx in windows:
                title = win32gui.GetWindowText(hwnd)
                label = f"[{idx}] {title or '(sin título)'}"
                self.window_combo.addItem(label, hwnd)
        self.window_combo.blockSignals(False)
        if self.window_combo.count() > 0:
            i = self.window_combo.findData(selected)
            self.window_combo.setCurrentIndex(i if i >= 0 else 0)
        self._on_window_selected()

    def _on_window_selected(self) -> None:
        key = self._window_key()
        cfg = self.window_configs.get(key or "", {}) if key else {}
        self.window_return_check.setChecked(bool(cfg.get("return_enabled", False)))
        coords = cfg.get("target_coords")
        if isinstance(coords, list) and len(coords) == 2:
            self.coord_x_input.setText(str(coords[0]))
            self.coord_y_input.setText(str(coords[1]))
        else:
            self.coord_x_input.clear()
            self.coord_y_input.clear()
        self.character_name_input.setText(str(cfg.get("character_name") or ""))
        target_map = cfg.get("target_map")
        if isinstance(target_map, str):
            idx = self.map_combo.findText(target_map)
            if idx >= 0:
                self.map_combo.setCurrentIndex(idx)
        self.auto_buy_potions_check.setChecked(bool(cfg.get("auto_buy_potions_enabled", False)))
        self.buy_mana_check.setChecked(bool(cfg.get("buy_mana_enabled", True)))
        try:
            mana_clicks = int(cfg.get("buy_mana_clicks", 10) or 0)
        except Exception:
            mana_clicks = 10
        self.buy_mana_clicks_input.setText(str(mana_clicks))

    def _save_current_window_config(self) -> None:
        key = self._window_key()
        if not key:
            QMessageBox.warning(self, "Ventana", "No hay ventana de juego seleccionada.")
            return

        character_name = self.character_name_input.text().strip()
        if not character_name:
            QMessageBox.warning(self, "Personaje", "Ingresa el nombre del personaje para esta ventana.")
            return

        enabled = self.window_return_check.isChecked()
        coords: list[int] | None = None
        target_map: str | None = None
        if enabled:
            x_txt = self.coord_x_input.text().strip()
            y_txt = self.coord_y_input.text().strip()
            if not x_txt.isdigit() or not y_txt.isdigit():
                QMessageBox.warning(self, "Coordenadas inválidas", "Debes escribir X e Y numéricos.")
                return
            coords = [int(x_txt), int(y_txt)]
            target_map = self.map_combo.currentText().strip()

        auto_buy_potions_enabled = self.auto_buy_potions_check.isChecked()
        buy_mana_enabled = self.buy_mana_check.isChecked()
        buy_mana_clicks_txt = self.buy_mana_clicks_input.text().strip() or "0"
        if not buy_mana_clicks_txt.isdigit():
            QMessageBox.warning(self, "Pociones", "Las cantidades de compra deben ser números enteros.")
            return
        buy_mana_clicks = int(buy_mana_clicks_txt)
        if auto_buy_potions_enabled and not buy_mana_enabled:
            QMessageBox.warning(self, "Pociones", "Activa compra de maná para usar compra automática.")
            return
        if auto_buy_potions_enabled and buy_mana_clicks <= 0:
            QMessageBox.warning(self, "Pociones", "La cantidad de clicks para maná debe ser mayor a 0.")
            return

        self.window_configs[key] = {
            "window_title": self.window_combo.currentText(),
            "character_name": character_name,
            "return_enabled": enabled,
            "target_coords": coords,
            "target_map": target_map,
            "auto_buy_potions_enabled": auto_buy_potions_enabled,
            "buy_mana_enabled": buy_mana_enabled,
            "buy_mana_clicks": buy_mana_clicks,
        }
        # Guarda solo ventanas detectadas actualmente para evitar hwnd obsoletos.
        active_keys = {f"hwnd_{int(hwnd)}" for hwnd, _idx in get_game_windows()}
        self.window_configs = {
            k: v for k, v in self.window_configs.items() if not k.startswith("hwnd_") or k in active_keys
        }
        self._save_window_configs()
        self.console.print_message(
            f"Configuración guardada para {character_name} ({key})",
            QColor(166, 227, 161),
        )

    def _identify_selected_window(self) -> None:
        hwnd = self.window_combo.currentData()
        if hwnd is None:
            QMessageBox.information(self, "Identificar ventana", "No hay una ventana válida seleccionada.")
            return
        try:
            win32gui.SetForegroundWindow(int(hwnd))
        except Exception as e:
            QMessageBox.warning(self, "Identificar ventana", f"No se pudo enfocar la ventana: {e}")
            return
        QMessageBox.information(
            self,
            "Identificar ventana",
            f"Se enfocó la ventana seleccionada:\n{self.window_combo.currentText()}",
        )

    def _collect_window_configs_for_thread(self) -> dict[int, dict[str, Any]]:
        out: dict[int, dict[str, Any]] = {}
        active_hwnds = {int(hwnd) for hwnd, _idx in get_game_windows()}
        for key, cfg in self.window_configs.items():
            if not key.startswith("hwnd_"):
                continue
            try:
                hwnd = int(key.split("_", 1)[1])
            except Exception:
                continue
            if hwnd not in active_hwnds:
                continue
            out[hwnd] = dict(cfg)
        return out

    def _refresh_telegram_badge(self) -> None:
        if os.path.exists(TELEGRAM_CONFIG_FILE):
            self.tg_status.setText("Configurado")
            self.tg_status.setStyleSheet("color: #a6e3a1; font-size: 12px; font-weight: 600;")
        else:
            self.tg_status.setText("Sin configurar")
            self.tg_status.setStyleSheet("color: #f38ba8; font-size: 12px;")

    def _set_license_chip(self, days: int | None) -> None:
        if days is None:
            self.license_chip.setText("Licencia: —")
            self.license_chip.setStyleSheet(
                "font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px;"
                "background-color: #313244; color: #bac2de;"
            )
            return
        hex_c, _tag = license_status_color_days(days)
        self.license_chip.setText(f"Licencia: {days}d")
        self.license_chip.setStyleSheet(
            "font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px;"
            f"background-color: #313244; color: {hex_c};"
        )

    def _show_system_info(self) -> None:
        res_x = win32api.GetSystemMetrics(0)
        res_y = win32api.GetSystemMetrics(1)
        self.console.print_message(
            f"Pantalla {res_x}×{res_y} · F4 inicia o detiene el helper",
            QColor(137, 180, 250),
        )
        days_left = get_license_days_left()
        self._set_license_chip(days_left)
        if days_left is not None:
            hex_c, _ = license_status_color_days(days_left)
            self.console.print_message(f"Días restantes de licencia: {days_left}", _qcolor_from_hex(hex_c))

    def _on_telegram_toggled(self, checked: bool) -> None:
        self.config_telegram_btn.setEnabled(checked)
        if checked and not os.path.exists(TELEGRAM_CONFIG_FILE):
            reply = QMessageBox.question(
                self,
                "Telegram",
                "¿Quieres configurar Telegram ahora?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._open_telegram_wizard()

    def _open_telegram_wizard(self) -> None:
        TelegramSetupWizard(self).exec()
        self._refresh_telegram_badge()

    def timerEvent(self, event) -> None:  # noqa: N802
        try:
            n = len(get_game_windows())
            self.windows_label.setText(f"Ventanas: {n}")
        except Exception:
            pass
        super().timerEvent(event)

    def toggle_healer(self) -> None:
        QMetaObject.invokeMethod(self, "_toggle_healer", Qt.QueuedConnection)

    @Slot()
    def _toggle_healer(self) -> None:
        if self._healer_active:
            self._stop_healer()
        else:
            self._start_healer()

    def _selected_game_hwnd(self) -> int | None:
        hwnd = self.window_combo.currentData()
        if hwnd is None:
            return None
        try:
            return int(hwnd)
        except (TypeError, ValueError):
            return None

    def _start_healer(self) -> None:
        if self.healer_thread and self.healer_thread.isRunning():
            return
        self._healer_active = True
        self.healer_status.setText("Activado")
        self.healer_status.setStyleSheet("font-weight: 700; font-size: 13px; color: #a6e3a1;")
        self.healer_thread = HealerThread(self._selected_game_hwnd)
        self.healer_thread.status_signal.connect(self.console.print_message)
        self.healer_thread.stopped_signal.connect(self._on_healer_stopped)
        self.healer_thread.start()

    def _stop_healer(self) -> None:
        if self.healer_thread and self.healer_thread.isRunning():
            self.healer_thread.stop()
            self.healer_thread.wait(3000)
        elif self._healer_active:
            self._on_healer_stopped()

    @Slot()
    def _on_healer_stopped(self) -> None:
        self._healer_active = False
        self.healer_thread = None
        self.healer_status.setText("Desactivado")
        self.healer_status.setStyleSheet("font-weight: 700; font-size: 13px; color: #bac2de;")
        self.console.print_message("Auto poción desactivado (Fin)", QColor(243, 139, 168))

    def toggle_script(self) -> None:
        QMetaObject.invokeMethod(self, "_toggle_script", Qt.QueuedConnection)

    @Slot()
    def _toggle_script(self) -> None:
        if self.thread and self.thread.isRunning():
            self.stop_thread()
        else:
            self.start_thread()

    def start_thread(self) -> None:
        if self.telegram_check.isChecked() and not os.path.exists(TELEGRAM_CONFIG_FILE):
            QMessageBox.warning(
                self,
                "Telegram",
                "Configura Telegram antes de iniciar o desactiva la casilla.",
            )
            return

        active_cfgs = self._collect_window_configs_for_thread()
        if not active_cfgs:
            QMessageBox.warning(self, "Ventanas", "No hay ventanas de juego activas para iniciar.")
            return
        for hwnd, cfg in active_cfgs.items():
            if not str(cfg.get("character_name") or "").strip():
                QMessageBox.warning(
                    self,
                    "Configuración incompleta",
                    f"Falta nombre de personaje en hwnd_{hwnd}.",
                )
                return

        self._set_controls_enabled(False)
        self._set_status_running()

        self.thread = MainThread(
            self.item_templates,
            helper_enabled=self.helper_check.isChecked(),
            cleaner_enabled=self.cleaner_check.isChecked(),
            pack_enabled=self.pack_check.isChecked(),
            telegram_enabled=self.telegram_check.isChecked(),
            pk_mode_enabled=self.pk_mode_check.isChecked(),
            window_configs=self._collect_window_configs_for_thread(),
        )
        self.thread.print_signal.connect(self.console.print_message)
        self.thread.scanning_signal.connect(self._set_scanning)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.license_expired_signal.connect(self._on_license_expired)
        self.thread.start()

    def stop_thread(self) -> None:
        if self.thread:
            self.thread.stop()
        self.status_pill.setText("Deteniendo…")
        self.status_pill.setStyleSheet("font-weight: 700; font-size: 13px; color: #fab387;")

    def _on_finished(self) -> None:
        self._set_controls_enabled(True)
        self._set_status_idle()
        self._set_scanning(False)

    @Slot()
    def _on_license_expired(self) -> None:
        if self.thread:
            self.thread.stop()
            self.thread.wait(8000)
        self.thread = None
        self._set_controls_enabled(True)
        self._set_status_idle()
        self._set_scanning(False)
        dlg = LicenseDialog(self, expired_mid_run=True)
        if dlg.exec() == QDialog.Accepted and check_license():
            self.start_thread()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.helper_check.setEnabled(enabled)
        self.cleaner_check.setEnabled(enabled)
        self.pack_check.setEnabled(enabled)
        self.telegram_check.setEnabled(enabled)
        self.pk_mode_check.setEnabled(enabled)
        self.window_combo.setEnabled(enabled)
        self.refresh_windows_btn.setEnabled(enabled)
        self.identify_window_btn.setEnabled(enabled)
        self.window_return_check.setEnabled(enabled)
        self.character_name_input.setEnabled(enabled)
        self.coord_x_input.setEnabled(enabled)
        self.coord_y_input.setEnabled(enabled)
        self.map_combo.setEnabled(enabled)
        self.auto_buy_potions_check.setEnabled(enabled)
        self.buy_mana_check.setEnabled(enabled)
        self.buy_mana_clicks_input.setEnabled(enabled)
        self.save_window_cfg_btn.setEnabled(enabled)
        self.config_telegram_btn.setEnabled(enabled and self.telegram_check.isChecked())
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)

    def _set_status_idle(self) -> None:
        self.status_pill.setText("Detenido")
        self.status_pill.setStyleSheet("font-weight: 700; font-size: 13px; color: #bac2de;")

    def _set_status_running(self) -> None:
        self.status_pill.setText("Ejecutando")
        self.status_pill.setStyleSheet("font-weight: 700; font-size: 13px; color: #a6e3a1;")

    def _set_scanning(self, active: bool) -> None:
        self.scanning = active
        if active:
            self.dot_count = 0
            self.dot_timer.start(450)
            self._update_scanning_dots()
        else:
            self.dot_timer.stop()
            if self.thread and self.thread.isRunning():
                self._set_status_running()
            else:
                self._set_status_idle()

    def _update_scanning_dots(self) -> None:
        if not self.scanning:
            return
        self.dot_count = (self.dot_count + 1) % 4
        dots = "·" * self.dot_count if self.dot_count else ""
        self.status_pill.setText(f"Escaneando {dots}".rstrip())
        self.status_pill.setStyleSheet("font-weight: 700; font-size: 13px; color: #89b4fa;")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(8000)
        if self.healer_thread and self.healer_thread.isRunning():
            self.healer_thread.stop()
            self.healer_thread.wait(3000)
        if self.listener is not None:
            try:
                self.listener.stop()
                join = getattr(self.listener, "join", None)
                if callable(join):
                    join(timeout=2.0)
            except Exception:
                pass
            self.listener = None
        super().closeEvent(event)
