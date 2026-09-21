"""
Generador de licencias RSA (solo autor).

Requisitos:
  - Instalar: cryptography, ntplib
  - Colocar `author_rsa_private.pem` en la carpeta del proyecto (o junto al .exe del generador),
    o definir MU_HELPER_RSA_PRIVATE_PATH con la ruta al PEM.

Salida: JSON firmado codificado en Base64 (una sola línea o agrupado con espacios).
El cliente verifica con la clave pública embebida (ofuscada) en mu_helper/license.py.

Para generar el par de claves (una sola vez):
  openssl genrsa -out author_rsa_private.pem 2048
  openssl rsa -in author_rsa_private.pem -pubout -out embedded_public.pem
  Luego ofuscar la pública con el script XOR del proyecto o actualizar _OBF_RSA_PUB_B64 en license.py.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import ntplib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from mu_helper.config import LICENSE_MAX_VALIDITY_DAYS


def _canonical_signed_bytes(payload: dict) -> bytes:
    sub = {"expire": str(payload["expire"]), "hwid": str(payload["hwid"]).strip().upper()}
    return json.dumps(sub, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_private_key() -> object:
    path = os.environ.get("MU_HELPER_RSA_PRIVATE_PATH", "").strip()
    pem_file = Path(path) if path else Path(_ROOT) / "author_rsa_private.pem"
    if not pem_file.is_file():
        raise FileNotFoundError(
            f"No se encuentra la clave privada: {pem_file}\n"
            "Genera el PEM (openssl) o define MU_HELPER_RSA_PRIVATE_PATH."
        )
    data = pem_file.read_bytes()
    return serialization.load_pem_private_key(data, password=None)


def _ntp_now() -> datetime:
    servers = ["pool.ntp.org", "time.windows.com", "time.google.com"]
    last: Exception | None = None
    c = ntplib.NTPClient()
    for s in servers:
        try:
            r = c.request(s, version=3, timeout=5.0)
            return datetime.fromtimestamp(r.tx_time)
        except Exception as e:
            last = e
            print(f"Aviso: NTP {s}: {e}", file=sys.stderr)
    raise RuntimeError("No se pudo obtener hora NTP.") from last


def generate_license_document(hwid: str, days: int) -> tuple[str, str]:
    hwid = hwid.strip().upper()
    if not hwid:
        raise ValueError("HWID vacío.")
    days = max(1, min(int(days), LICENSE_MAX_VALIDITY_DAYS))
    now = _ntp_now().date()
    expire = now + timedelta(days=days)
    expire_str = expire.strftime("%Y-%m-%d")
    payload = {
        "hwid": hwid,
        "expire": expire_str,
        "issued_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    priv = _load_private_key()
    msg = _canonical_signed_bytes(payload)
    sig = priv.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    doc = {"payload": payload, "signature": base64.b64encode(sig).decode("ascii")}
    raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    grouped = " ".join(b64[i : i + 5] for i in range(0, len(b64), 5))
    return grouped, expire_str


def main() -> None:
    ap = argparse.ArgumentParser(description="Generador de licencias RSA — Ultimate Mu Helper")
    ap.add_argument("--hwid", help="ID del equipo (mayúsculas)")
    ap.add_argument("--days", type=int, help=f"Días de validez (máx. {LICENSE_MAX_VALIDITY_DAYS})")
    args = ap.parse_args()

    print("=== Generador de licencias RSA — Ultimate Mu Helper ===\n")
    print(f"Periodo máximo por clave (cliente): {LICENSE_MAX_VALIDITY_DAYS} días.\n")

    if args.hwid:
        hwid = args.hwid.strip().upper()
    else:
        hwid = input("ID del equipo: ").strip().upper()
    if not hwid:
        print("ID requerido.")
        raise SystemExit(1)

    if args.days is not None:
        days = args.days
    else:
        raw = input(f"Días de validez (predeterminado {LICENSE_MAX_VALIDITY_DAYS}): ").strip()
        days = int(raw) if raw else LICENSE_MAX_VALIDITY_DAYS

    if days > LICENSE_MAX_VALIDITY_DAYS:
        print(f"Aviso: se limitará a {LICENSE_MAX_VALIDITY_DAYS} días (tope del cliente).")
        days = LICENSE_MAX_VALIDITY_DAYS

    try:
        activation_key, expire = generate_license_document(hwid, days)
    except Exception as e:
        print(f"No se pudo generar: {e}")
        raise SystemExit(1)

    print("\n--- Licencia generada ---")
    print(f"Equipo: {hwid}")
    print(f"Expira: {expire}")
    print(f"Clave (agrupada con espacios): {activation_key}")
    print(f"Clave compacta: {activation_key.replace(' ', '')}")


if __name__ == "__main__":
    main()
