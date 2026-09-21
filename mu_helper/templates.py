"""Carga de plantillas OpenCV."""

from __future__ import annotations

from typing import Any

import cv2

from mu_helper.config import ALL_TEMPLATES, GRAYSCALE_TEMPLATE_NAMES, IMAGES_DIR_NAME
from mu_helper.logging_utils import write_log
from mu_helper.template_paths import resolve_template_path


def load_item_templates() -> dict[str, Any]:
    item_templates: dict[str, Any] = {}
    for item_file in ALL_TEMPLATES:
        path_obj = resolve_template_path(item_file)
        if path_obj is None:
            write_log(
                f"Plantilla no encontrada: {item_file} "
                f"(buscada en '{IMAGES_DIR_NAME}/' y en la carpeta del programa)",
                "WARNING",
            )
            continue
        path = str(path_obj)
        flag = (
            cv2.IMREAD_GRAYSCALE
            if item_file in GRAYSCALE_TEMPLATE_NAMES
            else cv2.IMREAD_COLOR
        )
        template = cv2.imread(path, flag)
        if template is not None:
            item_templates[item_file] = template
            write_log(f"Plantilla cargada: {path}")
        else:
            write_log(f"No se pudo leer plantilla: {path}", "WARNING")
    return item_templates
