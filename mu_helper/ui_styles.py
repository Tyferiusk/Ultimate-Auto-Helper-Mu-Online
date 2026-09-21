"""Tema oscuro minimalista (inspirado en Catppuccin / referencia Muhelperclaude)."""

from __future__ import annotations

# Paleta base (aprox. Catppuccin Mocha)
_BASE = "#1e1e2e"
_MANTLE = "#181825"
_SURFACE0 = "#313244"
_SURFACE1 = "#45475a"
_OVERLAY0 = "#6c7086"
_TEXT = "#cdd6f4"
_SUBTEXT = "#bac2de"
_BLUE = "#89b4fa"

APP_STYLESHEET = f"""
QMainWindow, QDialog, QWizard {{
    background-color: {_BASE};
    color: {_TEXT};
}}
QWidget {{
    font-family: "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 13px;
    color: {_TEXT};
    background-color: transparent;
}}
QFrame#statusBarFrame {{
    background-color: {_MANTLE};
    border: 1px solid {_SURFACE0};
    border-radius: 8px;
}}
QLabel#appTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {_TEXT};
    letter-spacing: -0.02em;
}}
QLabel#appSubtitle {{
    font-size: 11px;
    color: {_OVERLAY0};
}}
QLabel#hintLabel {{
    font-size: 12px;
    color: {_SUBTEXT};
}}
QLabel#windowsLabel {{
    font-size: 12px;
    color: {_OVERLAY0};
}}
QLabel#licenseChip {{
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    background-color: {_SURFACE0};
    color: {_SUBTEXT};
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid {_SURFACE1};
    border-radius: 8px;
    margin-top: 8px;
    padding: 10px 8px 8px 8px;
    background-color: {_BASE};
    color: {_BLUE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 6px;
    color: {_BLUE};
}}
QCheckBox {{
    spacing: 8px;
    color: {_TEXT};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {_SURFACE1};
    background: {_SURFACE0};
}}
QCheckBox::indicator:checked {{
    background: {_BLUE};
    border-color: {_BLUE};
}}
QPushButton {{
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    background: {_SURFACE0};
    color: {_TEXT};
    border: 1px solid {_SURFACE1};
    min-height: 20px;
}}
QPushButton:hover {{
    background: {_SURFACE1};
    border-color: #585b70;
}}
QPushButton:pressed {{
    background: #45475a;
    padding-top: 7px;
    padding-bottom: 5px;
    border-color: #89b4fa;
}}
QPushButton:disabled {{
    color: #585b70;
    border-color: {_SURFACE0};
    background: {_MANTLE};
}}
QPushButton#primary {{
    background: #40a02b;
    color: #ffffff;
    border: 1px solid #2f8f1f;
}}
QPushButton#primary:hover {{
    background: #4cb83a;
}}
QPushButton#danger {{
    background: #e64553;
    color: #ffffff;
    border: 1px solid #c9303e;
}}
QPushButton#danger:hover {{
    background: #f0616e;
}}
QPushButton#ghost {{
    background: transparent;
    border: 1px dashed {_SURFACE1};
    color: {_SUBTEXT};
}}
QPushButton#ghost:hover {{
    background: {_SURFACE0};
    border-style: solid;
}}
QLineEdit {{
    border: 1px solid {_SURFACE1};
    border-radius: 6px;
    padding: 5px 8px;
    background: {_MANTLE};
    color: {_TEXT};
    selection-background-color: #45475a;
    selection-color: {_TEXT};
}}
QLineEdit:focus {{
    border-color: {_BLUE};
}}
QTextEdit {{
    background: {_MANTLE};
    color: {_TEXT};
    border: 1px solid {_SURFACE0};
    border-radius: 6px;
    padding: 8px;
}}
QTabWidget::pane {{
    border: 1px solid {_SURFACE1};
    border-radius: 8px;
    top: -1px;
    background: {_BASE};
    padding: 4px;
}}
QTabBar::tab {{
    background: {_SURFACE0};
    color: {_SUBTEXT};
    padding: 6px 12px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid {_SURFACE1};
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {_SURFACE1};
    color: {_BLUE};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: #3b3d52;
}}
QFrame#vLine {{
    color: {_SURFACE1};
    max-width: 1px;
}}
QScrollBar:vertical {{
    width: 10px;
    background: {_MANTLE};
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {_SURFACE1};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #585b70;
}}
QScrollBar:horizontal {{
    height: 10px;
    background: {_MANTLE};
}}
QScrollBar::handle:horizontal {{
    background: {_SURFACE1};
    border-radius: 5px;
    min-width: 28px;
}}
QMessageBox {{
    background-color: {_BASE};
}}
QMessageBox QLabel {{
    color: {_TEXT};
    min-width: 280px;
}}
QWizard {{
    background: {_BASE};
}}
QWizardPage {{
    background: {_BASE};
}}
QLabel#dlgTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {_TEXT};
}}
QLabel#dlgBody {{
    color: {_SUBTEXT};
}}
"""


def apply_app_style(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
