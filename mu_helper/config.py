"""Constantes de la aplicación (rutas, regiones, plantillas, licencia, mapas)."""

import os
import sys
from pathlib import Path


def app_root_dir() -> Path:
    """
    Carpeta de datos junto al .exe (PyInstaller onefile) o carpeta del proyecto en desarrollo.
    No usar __file__ bajo 'frozen': apunta a _MEIPASS y rompe rutas a license.dat / imagenes.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = app_root_dir()

IMAGES_DIR_NAME = "imagenes"

LICENSE_FILE = "license.dat"
LOG_FILE = "UltimateMuHelper_log.txt"
TELEGRAM_CONFIG_FILE = "telegram_config.json"
WINDOW_CONFIG_FILE = "window_config.json"

LICENSE_MAX_VALIDITY_DAYS = 30

# Mutex: una instancia por sesión de usuario (Local evita requerir permisos de administrador).
SINGLE_INSTANCE_MUTEX_NAME = "Local\\UltimateMuHelper_SingleInstance_7c4a2b91"

# NTP
NTP_TIMEOUT_SEC = 5.0
NTP_CACHE_MAX_AGE_SEC = 300.0
GRACE_DAYS_WITHOUT_NTP = 7

# Ruta fija preferida (sin depender de PATH). Puede sobreescribirse con MU_HELPER_TESSERACT_CMD.
TESSERACT_CMD = os.environ.get(
    "MU_HELPER_TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
).strip()

WINDOW_TITLE = "www.mu-exilio.com"

REGION_OFFLINE = (4, 454, 139, 40)
MATCH_THRESHOLD = 0.8
CHECK_INTERVAL = 0.2
SCANCODE_HOME = 0x47
MANA_REGION = (628, 600, 30, 17)
MANA_STABLE_SECONDS = 5.0
VIDA_REGION = (149, 598, 31, 13)
VIDA_STABLE_SECONDS = 20.0
POTION_REGION = (310, 582, 25, 22)
POTION_TEMPLATE = "potion_mana.png"
POTION_THRESHOLD = 0.8

INVENTORY_OPEN_REGION = (648, 40, 65, 15)
INVENTORY_OPEN_TEMPLATE = "inventario_abierto.png"
INVENTORY_OPEN_THRESHOLD = 0.8
INVENTORY_OPEN_CHECK_INTERVAL = 10.0

POPUP_OK_REGION = (365, 238, 74, 26)
POPUP_OK_TEMPLATE = "popup_ok.png"
POPUP_OK_THRESHOLD = 0.8
CITY_POPUP_REGION = (293, 190, 211, 77)
CITY_POPUP_TEMPLATE = "inside_city.png"
CITY_POPUP_THRESHOLD = 0.75
MINIMAP_OPEN_REGION = (770, 30, 30, 27)
MINIMAP_OPEN_TEMPLATE = "minimap_open.png"
MINIMAP_OPEN_THRESHOLD = 0.75

SLOT_VACIO_TEMPLATE = "slot_vacio.png"
SLOT_VACIO_THRESHOLD = 0.75
INVENTORY_FULL_CHECK_INTERVAL = 60.0

INVENTORY_REGION = (580, 273, 206, 206)
GROUND_REGION = (10, 229, 542, 200)
CONFIDENCE = 0.75
JEWEL_CONFIDENCE = 0.80
ITEMS_TO_CLEAN = [
    "medalla_oro.png",
    "medalla_plata.png",
    "corazon.png",
    "caja_suerte.png",
    "caja_cielo.png",
    "estrellas.png",
]
JEWELS = ["soul.png", "bless.png", "life.png", "chaos.png"]
GRAB_WAIT = 0.1
DROP_WAIT = 0.1
MOVE_DURATION = (0.05, 0.1)
PRE_DROP_PAUSE = 0.05
PACK_COOLDOWN = 60
SCANCODE_RETURN = 0x1C
SCANCODE_I = 0x17
SCANCODE_LCTRL = 0x1D
SCANCODE_Q = 0x10
SCANCODE_W = 0x11

# Auto poción (Healer): pausa entre ciclos Q→W
HEALER_CYCLE_PAUSE_SEC = 0.02
HEALER_KEY_PRESS_SEC = 0.012

# Retorno automático al spot tras muerte
COORD_SCAN_REGION = (22, 602, 50, 16)
# OCR por tramos separados (evita ambigüedades al leer dos números juntos).
COORD_SCAN_REGION_A = (16, 600, 26, 15)
COORD_SCAN_REGION_B = (42, 600, 26, 15)
CHAR_CENTER_RELATIVE = (398, 315)
MOVE_CLICK_OFFSET = 175
MOVE_UNSTUCK_OFFSET = MOVE_CLICK_OFFSET + 50
MOVE_STEP_PAUSE = 0.35
MAX_RETURN_STEPS_PER_WINDOW = 500
# Anti-atasco frecuente (retorno al spot / OCR): si las coords leí no cambian, clicks más largos
# para intentar salir sin reiniciar el flujo. Distinto del reinicio completo más abajo.
RETURN_UNSTUCK_LONG_CLICK_AFTER_SEC = 3.0
# Último recurso en "volver al spot": si tras los anti-atascos anteriores las coords OCR
# siguen igual durante este tiempo, se asume que no puede salir y se reinicia el retorno (TP+OCR).
SPOT_RETURN_STALL_RESTART_SEC = 20.0

# Lista de mapas (ventana M): región relativa a la ventana del juego (x, y, w, h)
MAP_LIST_REGION = (39, 40, 217, 422)
MAP_SELECTION_THRESHOLD = 0.75
WAIT_AFTER_TELEPORT = 3.0
# TAB abierto: área completa visible del mapa y triángulo rojo centrado.
TAB_MAP_REGION = (0, 28, 801, 536)
TAB_TRIANGLE_CENTER = (411, 319)
TAB_TRIANGLE_SIZE = (6, 3)

# Compra automática de pociones
POTION_BUY_MAP_NAME = "Danger"
POTION_BUY_NAV_MAP_NAME = "Tarkan2"
POTION_BUY_NPC_TARGET_COORDS = (192, 27)
NPC_POTION_SEARCH_REGION = (294, 25, 505, 538)
NPC_POTION_TEMPLATE = "npc_pociones.png"
NPC_POTION_THRESHOLD = 0.45
MERCHANT_OPEN_REGION = (404, 39, 76, 19)
MERCHANT_OPEN_TEMPLATE = "merchant_open.png"
# Región (ventana del juego) donde buscar la poción de maná en la UI del mercader abierto.
POTION_BUY_REGION = (516, 108, 31, 33)
POTION_BUY_MANA_TEMPLATE = "pocion_mana_compra.png"
POTION_BUY_MAP_TEMPLATE = "danger_map.png"
POTION_BUY_MANA_THRESHOLD = 0.66
POTION_BUY_CLICK_DELAY = 1.0
NPC_OPEN_RETRY_DELAY = 2.0
NPC_OPEN_MAX_RETRIES = 8

# Intervalo de polling para comandos Telegram (segundos)
TELEGRAM_POLL_INTERVAL = 30

RESPAWN_MAP_DISPLAY_NAMES: tuple[str, ...] = (
    "Lorencia",
    "Devias3",
    "Devias4",
    "Dungeon",
    "Dungeon2",
    "Dungeon3",
    "Atlans2",
    "Atlans3",
    "LostTower3",
    "LostTower4",
    "LostTower5",
    "LostTower6",
    "LostTower7",
    "Tarkan2",
    "Icarius",
    "Icarius2",
    "Exile",
)


# Rutas especiales SOLO donde el TP por M no basta: hay que entrar a pie tras un gateway.
#
# - Exile (Exilio): NO va aquí. Se elige en M como cualquier mapa y, ya dentro, el bot camina
#   al spot solo con OCR (igual que en Icarius2 después de cruzar el portal).
# - Icarius2: SÍ requiere ruta. Primero M → Icarius (gateway), luego la secuencia de clicks
#   hacia el portal (post_walk_*). Tras eso, el retorno al spot es OCR puro como siempre.
SPECIAL_MAP_ROUTES: dict[str, dict] = {
    "Icarius2": {
        "gateway_map": "Icarius",
        "post_walk_steps": ["left", "down", "down", "left", "left", "down"],
        "post_walk_click_delay": 0.9,
        "post_walk_settle": 2.5,
    },
}


def map_template_filename(map_display_name: str) -> str:
    return f"{map_display_name.lower().replace(' ', '_')}_map.png"


MAP_TEMPLATE_FILENAMES: tuple[str, ...] = tuple(
    map_template_filename(n) for n in RESPAWN_MAP_DISPLAY_NAMES
)

ALL_TEMPLATES = (
    list(ITEMS_TO_CLEAN)
    + list(JEWELS)
    + list(MAP_TEMPLATE_FILENAMES)
    + [
        "online.png",
        "offline.png",
        POTION_TEMPLATE,
        POTION_BUY_MAP_TEMPLATE,
        NPC_POTION_TEMPLATE,
        MERCHANT_OPEN_TEMPLATE,
        POTION_BUY_MANA_TEMPLATE,
        INVENTORY_OPEN_TEMPLATE,
        POPUP_OK_TEMPLATE,
        CITY_POPUP_TEMPLATE,
        MINIMAP_OPEN_TEMPLATE,
        SLOT_VACIO_TEMPLATE,
    ]
)

GRAYSCALE_TEMPLATE_NAMES = frozenset(
    {
        "online.png",
        "offline.png",
        POTION_TEMPLATE,
        POTION_BUY_MAP_TEMPLATE,
        NPC_POTION_TEMPLATE,
        MERCHANT_OPEN_TEMPLATE,
        POTION_BUY_MANA_TEMPLATE,
        INVENTORY_OPEN_TEMPLATE,
        POPUP_OK_TEMPLATE,
        CITY_POPUP_TEMPLATE,
        MINIMAP_OPEN_TEMPLATE,
        SLOT_VACIO_TEMPLATE,
    }
)

SKIP_IN_FIND_ITEMS = frozenset(
    {
        "online.png",
        "offline.png",
        POTION_TEMPLATE,
        POTION_BUY_MAP_TEMPLATE,
        NPC_POTION_TEMPLATE,
        MERCHANT_OPEN_TEMPLATE,
        POTION_BUY_MANA_TEMPLATE,
        INVENTORY_OPEN_TEMPLATE,
        POPUP_OK_TEMPLATE,
        CITY_POPUP_TEMPLATE,
        MINIMAP_OPEN_TEMPLATE,
        SLOT_VACIO_TEMPLATE,
    }
) | frozenset(MAP_TEMPLATE_FILENAMES)
