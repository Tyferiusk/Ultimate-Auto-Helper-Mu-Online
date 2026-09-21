# Ultimate Auto Helper MuOnline

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-Proprietary-red)

Asistente de automatización para **Mu Online** con interfaz gráfica moderna, sistema de licencias RSA + HWID, notificaciones por Telegram y detección por visión por computadora (OpenCV + OCR).

---

## 📋 Tabla de contenidos

- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Configuración](#-configuración)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Compilación a .exe](#-compilación-a-exe)
- [Sistema de licencias](#-sistema-de-licencias)
- [Solución de problemas](#-solución-de-problemas)
- [Aviso legal](#-aviso-legal)

---

## ✨ Características

### 🤖 Auto Helper
- Detecta cuando el helper del juego pasa a estado **OFFLINE** y lo reactiva automáticamente.
- Envía `HOME` para reanudar el ataque.
- Detecta el popup *"auto attack activated outside the city"* y lo cierra con `ENTER`.

### 🧹 Limpieza de inventario
- Detecta y arrastra al suelo objetos no deseados:
  - Medallas de oro/plata, corazón, caja de suerte, caja cielo, estrellas.

### 💎 Empaquetado de joyas
- Cuenta joyas (Soul, Bless, Life, Chaos) en el inventario.
- Envía `/pack <joya> 10` automáticamente al alcanzar 10 unidades (con cooldown configurable).

### 💚 Auto poción (Healer)
- Alterna rápidamente **Q → W** en serie sobre la ventana seleccionada.
- Se activa/desactiva con la tecla **Fin** sin necesidad de detener el helper.

### 🏃 Retorno automático al spot tras morir
- Detección de muerte por popup de ciudad.
- OCR de coordenadas (EasyOCR) para navegar de vuelta al spot.
- Teletransporte por lista de mapas (`M`).
- Anti-atascos: clics largos, inversión automática de ejes y reinicio de ruta.

### 🧪 Compra automática de pociones
- Cuando se queda sin pociones de maná, viaja al NPC, abre el mercader y compra la cantidad configurada.
- Ruta especial soportada (ej. `Icarius2` con pasos manuales).

### 📱 Notificaciones Telegram
- Muerte del personaje.
- Inventario lleno.
- Falta de pociones.
- Compra completada.
- Comandos remotos (`/request auto`) para reactivar el helper desde el móvil.

### 🖥️ Multi-ventana
- Soporte para múltiples clientes de Mu Online abiertos simultáneamente.
- Configuración independiente por personaje/ventana (retorno, coordenadas, mapa, compra).
- Las acciones críticas (retorno/compra) pausan el resto de ventanas para evitar interferencias.

### 🔐 Seguridad
- Licencia firmada con **RSA-2048** + **DPAPI** (Windows).
- **HWID** reforzado (placa base, CPU, disco, MAC).
- Verificación de hora por **NTP** con periodo de gracia de 7 días.
- **Instancia única** vía mutex nombrado.
- **Elevación UAC** automática.

---

## 🧩 Requisitos

- **Windows 10/11** (x64)
- **Python 3.10+** (solo si ejecutas desde código fuente)
- **Tesseract OCR** (opcional, para OCR alternativo)
- **EasyOCR** (se instala vía pip, descarga modelos en el primer uso)

### Dependencias Python

```bash
pip install PySide6 opencv-python mss numpy pywin32 pyautogui pynput \
            easyocr ntplib WMI cryptography requests
```

---

## 🚀 Instalación

### Opción 1 — Ejecutable precompilado
1. Descarga el `.exe` desde la sección de *Releases*.
2. Coloca la carpeta `imagenes/` junto al ejecutable.
3. Coloca tu archivo `license.dat` en la misma carpeta (o actívalo la primera vez con tu clave).
4. Ejecuta `UltimateMuHelper.exe` (se solicitará UAC).

### Opción 2 — Desde código fuente

```bash
git clone https://github.com/<tu-usuario>/ultimate-mu-helper.git
cd ultimate-mu-helper
pip install -r requirements.txt
python main.py
```

> El programa solicitará privilegios de administrador (necesario para enviar teclas a ventanas del juego).

---

## 🎮 Uso

1. **Inicia Mu Online** y asegúrate de que el título de la ventana contenga `www.mu-exilio.com`.
2. **Ejecuta Ultimate Mu Helper**.
3. En la pestaña **Control**:
   - Marca las funciones deseadas (`Auto Helper`, `Limpiar inventario`, `Pack de joyas`, etc.).
   - Selecciona la ventana del juego en el desplegable.
   - Configura **nombre del personaje**, **coordenadas del spot**, **mapa** y **compra automática**.
   - Pulsa **Guardar configuración**.
4. Pulsa **Iniciar** (o la tecla **F4**).
5. Pestaña **Healer**: pulsa **Fin** para activar/desactivar el auto poción.

### Atajos globales

| Tecla | Acción |
|-------|--------|
| `F4`  | Iniciar / Detener el helper |
| `Fin` | Activar / Desactivar auto poción |

---

## ⚙️ Configuración

### Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `license.dat` | Licencia cifrada con DPAPI (no compartir) |
| `telegram_config.json` | Token y chat ID del bot |
| `window_config.json` | Configuración por ventana/personaje |
| `UltimateMuHelper_log.txt` | Log de actividad |

### Carpeta `imagenes/`

Contiene las plantillas PNG que el bot usa para reconocimiento visual:

- **Mapas:** `lorencia_map.png`, `devias3_map.png`, `tarkan2_map.png`, etc.
- **Objetos a limpiar:** `medalla_oro.png`, `corazon.png`, `caja_suerte.png`, etc.
- **Joyas:** `soul.png`, `bless.png`, `life.png`, `chaos.png`.
- **UI:** `online.png`, `offline.png`, `popup_ok.png`, `inside_city.png`, `minimap_open.png`, etc.

> Las plantillas deben capturarse a la **misma resolución** con la que se ejecutará el bot.

### Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `MU_HELPER_TESSERACT_CMD` | Ruta personalizada a `tesseract.exe` |
| `MU_HELPER_SKIP_ADMIN` | Si está definida, no relanza como admin (útil en desarrollo) |

---

## 📁 Estructura del proyecto

```
ultimate-mu-helper/
├── main.py                  # Punto de entrada
├── requirements.txt
├── README.md
├── mu_cleaner.ico
├── imagenes/                # Plantillas PNG
│   ├── lorencia_map.png
│   ├── offline.png
│   └── ...
└── mu_helper/
    ├── __init__.py          # Versión del paquete
    ├── config.py            # Constantes y regiones
    ├── elevate_admin.py     # Elevación UAC
    ├── game_thread.py       # Hilo principal de automatización
    ├── healer_thread.py     # Hilo de auto poción
    ├── license.py           # Sistema RSA + DPAPI + NTP
    ├── logging_utils.py     # Log a archivo
    ├── single_instance.py   # Mutex de instancia única
    ├── template_paths.py    # Resolución de rutas de plantillas
    ├── templates.py         # Carga de plantillas OpenCV
    ├── ui_dialogs.py        # Diálogos de licencia y Telegram
    ├── ui_main.py           # Ventana principal
    ├── ui_styles.py         # Tema oscuro (Catppuccin)
    ├── win_input.py         # Entrada Win32 (teclas/ratón)
    └── window_finder.py     # Detección de ventanas del juego
```

---

## 📦 Compilación a .exe

Con **PyInstaller**:

```bash
pyinstaller --noconfirm --onefile --windowed ^
  --name "UltimateMuHelper" ^
  --icon "mu_cleaner.ico" ^
  --add-data "imagenes;imagenes" ^
  --hidden-import easyocr ^
  --hidden-import win32crypt ^
  main.py
```

> El ejecutable buscará `imagenes/`, `license.dat` y los JSON de configuración **junto al .exe** (no dentro del bundle).

---

## 🔐 Sistema de licencias

- **Formato:** `license.dat` = `CryptProtectData(JSON)` con `{rsa_document, state}`.
- **Firma:** RSA-2048 PKCS#1 v1.5 + SHA-256 sobre `{expire, hwid}`.
- **HWID:** SHA-256 truncado de placa base + CPU + disco + MAC.
- **Validez máxima:** 30 días por clave (configurable).
- **Hora de confianza:** NTP (`pool.ntp.org`, `time.windows.com`, `time.google.com`).
- **Gracia sin NTP:** 7 días desde el último sync.
- **Re-verificación:** cada 12 horas en ejecución.

La clave de activación (Base64) solo la emite el autor con su clave privada.

---

## 🛠️ Solución de problemas

| Problema | Solución |
|----------|----------|
| No detecta ventanas del juego | Verifica que el título contenga `www.mu-exilio.com` y que el cliente esté en ventana (no pantalla completa exclusiva). |
| No envía teclas | Ejecuta como administrador. |
| OCR no lee coordenadas | Asegúrate de que la resolución sea la esperada (regiones en `config.py`). |
| EasyOCR tarda la primera vez | Descarga modelos (~100 MB). Requiere Internet solo la primera ejecución. |
| Licencia "HWID incorrecto" | Cambiaste hardware. Solicita una clave nueva al autor. |
| "Periodo de gracia NTP agotado" | Conecta a Internet para sincronizar la hora. |

Los detalles se registran en `UltimateMuHelper_log.txt`.

---

## ⚠️ Aviso legal

Este software se distribuye **únicamente con fines educativos y de automatización personal**.

- El uso de herramientas de automatización puede violar los **Términos de Servicio** de Mu Online y de sus servidores privados.
- El autor **no se responsabiliza** por baneos, sanciones o pérdidas derivadas del uso de este programa.
- **No compartas** tu archivo `license.dat` ni tu clave de activación.
- Este proyecto **no está afiliado** a Webzen, MU Online ni a `mu-exilio.com`.

Úsalo bajo tu propia responsabilidad.

---

## 📄 Licencia

Software **propietario**. Todos los derechos reservados.

No se permite la redistribución, modificación ni uso comercial sin autorización expresa del autor.

---

## 👤 Autor

**Tyferiusk**

Si te resultó útil, considera invitarme un café ☕ o darle una ⭐ al repositorio.

---

## 🙏 Créditos

- Inspirado en el estilo visual de [Catppuccin](https://github.com/catppuccin/catppuccin).
- OCR potenciado por [EasyOCR](https://github.com/JaidedAI/EasyOCR).
- Captura de pantalla por [mss](https://github.com/BoboTiG/python-mss).
- GUI con [PySide6](https://doc.qt.io/qtforpython/).
