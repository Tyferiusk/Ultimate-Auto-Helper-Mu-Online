"""Resolución de rutas a plantillas PNG (carpeta imagenes/ o raíz de la app)."""

from __future__ import annotations

from pathlib import Path

from mu_helper.config import BASE_DIR, IMAGES_DIR_NAME


def resolve_template_path(filename: str) -> Path | None:
    """Prioridad: imagenes/<archivo> luego <archivo> en la raíz de la app."""
    p = BASE_DIR / IMAGES_DIR_NAME / filename
    if p.is_file():
        return p
    p2 = BASE_DIR / filename
    if p2.is_file():
        return p2
    return None
