"""Diálogos de licencia y Telegram (adaptados al tema oscuro global)."""

from __future__ import annotations

import json
import os

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from mu_helper.config import TELEGRAM_CONFIG_FILE
from mu_helper.license import (
    activate_license_from_key,
    get_hardware_id,
    get_license_failure_message,
    refresh_trusted_time_anchor,
)


class LicenseDialog(QDialog):
    """Diálogo de licencia: sin licencia, caducada, HWID, formato inválido, etc."""

    def __init__(self, parent=None, *, expired_mid_run: bool = False):
        super().__init__(parent)
        self._expired_mid_run = expired_mid_run
        self.setWindowTitle("Licencia — Ultimate Mu Helper")
        self.setMinimumSize(480, 280)
        self.resize(500, 320)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Licencia caducada o inválida" if expired_mid_run else "Activación de licencia")
        title.setObjectName("dlgTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        hint = get_license_failure_message()
        if hint.strip():
            reason = QLabel(hint)
            reason.setWordWrap(True)
            reason.setStyleSheet("color: #fab387; font-size: 12px;")
            layout.addWidget(reason)

        info = QLabel(
            "Pega la clave RSA en Base64 emitida por el autor. "
            "Hace falta Internet (NTP) la primera vez o al activar."
        )
        info.setObjectName("dlgBody")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("Pega la clave (puede llevar espacios entre grupos)")
        layout.addWidget(self.license_input)

        hwid = get_hardware_id()
        hwid_label = QLabel(f"ID de este equipo: <b>{hwid}</b>")
        hwid_label.setTextFormat(Qt.RichText)
        hwid_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hwid_label.setObjectName("dlgBody")
        layout.addWidget(hwid_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.activate_btn = QPushButton("Ingresar nueva licencia")
        self.activate_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("Salir")
        self.cancel_btn.setObjectName("ghost")
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.activate_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.activate_btn.clicked.connect(self.activate_license)
        self.cancel_btn.clicked.connect(self.reject)

    def activate_license(self) -> None:
        key = self.license_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Error", "Introduce una clave.")
            return
        try:
            refresh_trusted_time_anchor()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo obtener la hora desde los servidores NTP:\n{e}",
            )
            return
        ok, err = activate_license_from_key(key.replace(" ", ""))
        if ok:
            self.accept()
        else:
            QMessageBox.warning(self, "No se pudo activar", err)


class TelegramSetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Telegram")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setFixedSize(580, 440)

        page1 = QWizardPage()
        page1.setTitle("Notificaciones Telegram")
        page1.setSubTitle("Configura el bot para recibir alertas en el móvil.")
        layout1 = QVBoxLayout(page1)
        intro = QLabel(
            "Necesitas:\n"
            "1. Un bot creado con @BotFather.\n"
            "2. El token del bot.\n"
            "3. Tu Chat ID personal."
        )
        intro.setObjectName("dlgBody")
        layout1.addWidget(intro)

        page2 = QWizardPage()
        page2.setTitle("Paso 1: token del bot")
        page2.setSubTitle("Crea el bot y copia el token.")
        layout2 = QVBoxLayout(page2)
        t1 = QLabel(
            "1. Abre Telegram y busca @BotFather.\n"
            "2. Envía /newbot y sigue las instrucciones.\n"
            "3. Copia el token que te entregue."
        )
        t1.setObjectName("dlgBody")
        layout2.addWidget(t1)
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("123456:ABC…")
        layout2.addWidget(QLabel("Token del bot:"))
        layout2.addWidget(self.token_edit)
        page2.registerField("token*", self.token_edit)

        page3 = QWizardPage()
        page3.setTitle("Paso 2: Chat ID")
        page3.setSubTitle("Identificador de tu chat con el bot.")
        layout3 = QVBoxLayout(page3)
        t2 = QLabel(
            "Opción A: busca @userinfobot en Telegram.\n\n"
            "Opción B: envía un mensaje a tu bot y revisa getUpdates en la API de Telegram."
        )
        t2.setObjectName("dlgBody")
        layout3.addWidget(t2)
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText("123456789")
        layout3.addWidget(QLabel("Chat ID:"))
        layout3.addWidget(self.chat_edit)
        page3.registerField("chat_id*", self.chat_edit)

        page4 = QWizardPage()
        page4.setTitle("Paso 3: verificar")
        page4.setSubTitle("Prueba la conexión antes de guardar.")
        layout4 = QVBoxLayout(page4)
        self.test_result = QLabel("Aún no se ha probado la conexión.")
        self.test_result.setWordWrap(True)
        self.test_result.setObjectName("dlgBody")
        layout4.addWidget(self.test_result)
        test_btn = QPushButton("Enviar mensaje de prueba")
        test_btn.clicked.connect(self.test_connection)
        layout4.addWidget(test_btn)
        layout4.addStretch()

        self.addPage(page1)
        self.addPage(page2)
        self.addPage(page3)
        self.addPage(page4)

        self.setButtonText(QWizard.FinishButton, "Guardar")
        self.finished.connect(self.save_config)

    def test_connection(self) -> None:
        token = self.field("token")
        chat_id = self.field("chat_id")
        if not token or not chat_id:
            self.test_result.setText("Token y Chat ID son obligatorios.")
            self.test_result.setStyleSheet("color: #f38ba8;")
            return
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "Conexión correcta. Ultimate Mu Helper.",
            }
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                self.test_result.setText("Conexión correcta. Revisa Telegram.")
                self.test_result.setStyleSheet("color: #a6e3a1;")
            else:
                err = r.json().get("description", "Error desconocido")
                self.test_result.setText(f"Falló: {err}")
                self.test_result.setStyleSheet("color: #f38ba8;")
        except Exception as e:
            self.test_result.setText(f"Error: {e}")
            self.test_result.setStyleSheet("color: #f38ba8;")

    def save_config(self) -> None:
        token = self.field("token")
        chat_id = self.field("chat_id")
        try:
            with open(TELEGRAM_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"token": token, "chat_id": chat_id}, f, indent=2)
        except OSError as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar: {e}")
            return
        QMessageBox.information(self, "Guardado", "Configuración de Telegram guardada.")
