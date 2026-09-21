"""
Licencia RSA + DPAPI (Windows), HWID reforzado, NTP con gracia y re-verificación.

license.dat: CryptProtectData(JSON UTF-8) con {"rsa_document": {...}, "state": {...}}.
El documento RSA solo lo firma el autor (clave privada fuera del cliente).
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import ntplib
import wmi
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from mu_helper.config import (
    BASE_DIR,
    GRACE_DAYS_WITHOUT_NTP,
    LICENSE_FILE,
    LICENSE_MAX_VALIDITY_DAYS,
    NTP_CACHE_MAX_AGE_SEC,
    NTP_TIMEOUT_SEC,
)
from mu_helper.logging_utils import write_log

_XOR_KEY = b"UH7kQ2wM9vLxN4pR1tY0zB3sA6cD8eF"


def _xor_deobf_b64(b64: str) -> bytes:
    raw = base64.b64decode(b64.encode("ascii"))
    return bytes(raw[i] ^ _XOR_KEY[i % len(_XOR_KEY)] for i in range(len(raw)))


def xor_strings(obfuscated_b64: str) -> bytes:
    """Decodifica string ofuscado (Base64 → XOR con clave interna)."""
    return _xor_deobf_b64(obfuscated_b64)


# Clave pública RSA (PEM) ofuscada (XOR + base64)
_OBF_RSA_PUB_B64 = (
    "eGUaRnxwMgpwOGwoG3Y8G3JUEnUjbx5ebBtpCXEsBBwidiUTVRw8UR0lP3dDQBBwJRx2OwN8MABnWwV1LA8XC1AgEnMmCHgcdDwPUBQQVAcgRhFwWRwRRQgXb28WBQ1gOBsCRiRaPRsPegRbGQYVGlksDgJCeANRCW8tDSILUBJ6dRYLfkQ9Nw0NWyB7OCMGHwYAH3BPMSJPXXUiQkEyKwsdBg0Cej0LAT4zSzEhfBsjBTQUdAk9UkoNHnFZGhUCHzsKHSoADHwAI0ISFWk/BRxDMEAlfHwtCDN6ZjFbezEvCjF6PR4DFQIETDdkNDp6NChxKgZSKC8YKk4dOFU6LgsUBD4FVzYHYDESVko7QDcEfywmEzdyLwwCAzwHDUddDnwAJAETZFtMDkdJFH5DJGJbLX4qJAQHTyUaVzV0XB57EQtRSBZDFhtmMXRyWAUBUnIIPRctElMlIFkwP1dCRkosUj4nXh48dBIHaSN4BhIzdQR0MysAXidjRTsOQBsgd0cUPFc2MwM5NUs6GVc2KAgcITIZDyoHXxMmCj4lEBo+PSV4MBhhOwA5XmwbTml9KwJ1GGIpHXs0bXIzFVVjGV1/"
)

# pool.ntp.org|time.windows.com|time.google.com
_OBF_NTP_LIST_B64 = "JSdYB39cAz0XGT4fMkAZP1RaLlkUJlwEMhgAK1UZMjwlUkU2XRgqVRNiGyFZDCZYGTweGS5cBiVQDyVKAGg2J1o="

_OBF_HWID_SALT_B64 = "GD1/Dj1CEj9xASUcHVUcJm4CaA=="


def _ntp_servers() -> list[str]:
    try:
        raw = _xor_deobf_b64(_OBF_NTP_LIST_B64)
        return [s.strip() for s in raw.decode("utf-8").split("|") if s.strip()]
    except Exception:
        return ["pool.ntp.org", "time.windows.com", "time.google.com"]


def _hwid_salt() -> str:
    try:
        return _xor_deobf_b64(_OBF_HWID_SALT_B64).decode("utf-8")
    except Exception:
        return "MuHelperHwidSalt_v1"


_rsa_public_key: rsa.RSAPublicKey | None = None


def _load_public_key() -> rsa.RSAPublicKey:
    global _rsa_public_key
    if _rsa_public_key is not None:
        return _rsa_public_key
    pem = _xor_deobf_b64(_OBF_RSA_PUB_B64)
    _rsa_public_key = serialization.load_pem_public_key(pem)
    assert isinstance(_rsa_public_key, rsa.RSAPublicKey)
    return _rsa_public_key


def _try_win32crypt():
    try:
        import win32crypt  # type: ignore

        return win32crypt
    except Exception:
        return None


def _license_path() -> Path:
    return Path(BASE_DIR) / LICENSE_FILE


def _dpapi_protect(blob: bytes) -> bytes:
    wc = _try_win32crypt()
    if wc is None:
        raise RuntimeError("win32crypt no disponible (instala pywin32).")
    out = wc.CryptProtectData(blob, "MuHelperLic", None, None, None, 0)
    # pywin32: a veces devuelve bytes completos; en otras versiones, tupla (desc, bytes).
    if isinstance(out, bytes):
        return out
    if isinstance(out, tuple) and len(out) >= 2 and isinstance(out[1], bytes):
        return out[1]
    raise TypeError(f"CryptProtectData devolvió tipo inesperado: {type(out)!r}")


def _dpapi_unprotect(blob: bytes) -> bytes:
    wc = _try_win32crypt()
    if wc is None:
        raise RuntimeError("win32crypt no disponible (instala pywin32).")
    out = wc.CryptUnprotectData(blob, None, None, None, 0)
    if isinstance(out, bytes):
        return out
    if isinstance(out, tuple) and len(out) >= 2 and isinstance(out[1], bytes):
        return out[1]
    raise TypeError(f"CryptUnprotectData devolvió tipo inesperado: {type(out)!r}")


def get_hardware_id() -> str:
    parts: list[str] = []
    try:
        c = wmi.WMI()
        for bb in c.Win32_BaseBoard():
            if bb.SerialNumber:
                parts.append(str(bb.SerialNumber).strip())
            break
        for proc in c.Win32_Processor():
            pid = getattr(proc, "ProcessorId", None) or getattr(proc, "UniqueId", None)
            if pid:
                parts.append(str(pid).strip())
            break
        for disk in c.Win32_LogicalDisk(DriveType=3):
            vsn = getattr(disk, "VolumeSerialNumber", None)
            if vsn:
                parts.append(str(vsn).strip())
            break
        for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            if nic.MacAddress:
                parts.append(str(nic.MacAddress).strip())
                break
    except Exception:
        pass
    if not parts:
        parts.append(socket.gethostname())
    raw = ("|".join(parts) + "|" + _hwid_salt()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32].upper()


def _canonical_signed_bytes(payload: dict[str, Any]) -> bytes:
    sub = {"expire": str(payload["expire"]), "hwid": str(payload["hwid"]).strip().upper()}
    return json.dumps(sub, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_rsa_document(doc: dict[str, Any]) -> dict[str, Any]:
    payload = doc.get("payload")
    sig_b64 = doc.get("signature")
    if not isinstance(payload, dict) or not isinstance(sig_b64, str):
        raise ValueError("Documento de licencia inválido.")
    if "expire" not in payload or "hwid" not in payload:
        raise ValueError("Payload incompleto.")
    sig = base64.b64decode(sig_b64.encode("ascii"))
    msg = _canonical_signed_bytes(payload)
    _load_public_key().verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
    return payload


def _load_file_blob() -> dict[str, Any] | None:
    path = _license_path()
    if not path.is_file():
        return None
    try:
        enc = path.read_bytes()
        if not enc:
            return None
        inner = _dpapi_unprotect(enc)
        return json.loads(inner.decode("utf-8"))
    except Exception as e:
        write_log(f"load license file: {e}", "WARNING")
        return None


def _save_file_blob(wrapper: dict[str, Any]) -> tuple[bool, str]:
    try:
        raw = json.dumps(wrapper, separators=(",", ":")).encode("utf-8")
        enc = _dpapi_protect(raw)
        _license_path().write_bytes(enc)
        return True, ""
    except Exception as e:
        msg = str(e)
        write_log(f"save license file: {msg}", "ERROR")
        return False, msg


_trusted_anchor: tuple[datetime, float] | None = None
_anchor_fetched_at_mono: float = 0.0


def get_ntp_time(server: str) -> datetime:
    client = ntplib.NTPClient()
    response = client.request(server, version=3, timeout=NTP_TIMEOUT_SEC)
    return datetime.fromtimestamp(response.tx_time)


def _fetch_ntp_datetime() -> datetime:
    last_err: Exception | None = None
    for srv in _ntp_servers():
        try:
            ntp_time = get_ntp_time(srv)
            write_log(f"Hora NTP obtenida de {srv}", "INFO")
            return ntp_time
        except Exception as e:
            last_err = e
            write_log(f"Fallo NTP {srv} (timeout {NTP_TIMEOUT_SEC}s): {e}", "WARNING")
    raise RuntimeError("No se pudo obtener la hora NTP.") from last_err


def refresh_trusted_time_anchor() -> datetime:
    """Fuerza una nueva consulta NTP y actualiza la ancla en memoria."""
    global _trusted_anchor, _anchor_fetched_at_mono
    ntp = _fetch_ntp_datetime()
    _trusted_anchor = (ntp, time.monotonic())
    _anchor_fetched_at_mono = _trusted_anchor[1]
    return ntp


def trusted_now() -> datetime:
    if _trusted_anchor is None:
        refresh_trusted_time_anchor()
    assert _trusted_anchor is not None
    ntp_dt, mono = _trusted_anchor
    return ntp_dt + timedelta(seconds=time.monotonic() - mono)


def get_trusted_time() -> datetime:
    """Hora de confianza: reutiliza ancla NTP reciente o refresca."""
    global _trusted_anchor, _anchor_fetched_at_mono
    if _trusted_anchor is not None:
        age = time.monotonic() - _anchor_fetched_at_mono
        if age < NTP_CACHE_MAX_AGE_SEC:
            return trusted_now()
    return refresh_trusted_time_anchor()


def _trusted_now_with_grace(wrapper: dict[str, Any] | None) -> datetime:
    try:
        return get_trusted_time()
    except Exception:
        pass
    if not wrapper:
        raise RuntimeError("Sin licencia y sin NTP.")
    st = wrapper.get("state") or {}
    wall = st.get("ntp_wall")
    iso = st.get("ntp_iso")
    if wall is None or not iso:
        raise RuntimeError("Sin referencia NTP previa; conecta a Internet al menos una vez.")
    if time.time() - float(wall) > GRACE_DAYS_WITHOUT_NTP * 86400:
        raise RuntimeError("Periodo de gracia NTP agotado (7 días sin sincronizar).")
    base = datetime.fromisoformat(str(iso))
    return base + timedelta(seconds=(time.time() - float(wall)))


def _merge_payload_state(wrapper: dict[str, Any]) -> dict[str, Any]:
    doc = wrapper.get("rsa_document")
    if not isinstance(doc, dict):
        raise ValueError("rsa_document ausente o inválido.")
    payload = verify_rsa_document(doc)
    st = wrapper.get("state")
    out = dict(payload)
    if isinstance(st, dict):
        for k, v in st.items():
            if k not in out:
                out[k] = v
    return out


def load_license_data() -> dict[str, Any] | None:
    try:
        w = _load_file_blob()
        if not w:
            return None
        return _merge_payload_state(w)
    except Exception as e:
        write_log(f"load_license_data: {e}", "WARNING")
        return None


def save_license_data(data: dict[str, Any]) -> bool:
    """Actualiza solo el estado local (last_check / ntp) conservando rsa_document."""
    try:
        w_old = _load_file_blob()
        if not w_old or not isinstance(w_old.get("rsa_document"), dict):
            return False
        verify_rsa_document(w_old["rsa_document"])
        st = dict(w_old.get("state") or {})
        for k in ("last_check", "ntp_wall", "ntp_iso"):
            if k in data:
                st[k] = data[k]
        w_old["state"] = st
        ok, _ = _save_file_blob(w_old)
        return ok
    except Exception as e:
        write_log(f"save_license_data: {e}", "ERROR")
        return False


def _validate_core(data: dict[str, Any], now: datetime) -> tuple[bool, str]:
    if data.get("hwid", "").strip().upper() != get_hardware_id():
        return False, "hwid"
    expire_str = data.get("expire")
    if not expire_str:
        return False, "formato"
    try:
        expire_d = datetime.strptime(str(expire_str), "%Y-%m-%d").date()
    except ValueError:
        return False, "formato"
    if now.date() > expire_d:
        return False, "caducada"
    last_check_str = data.get("last_check")
    if last_check_str:
        try:
            last_check = datetime.strptime(str(last_check_str), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            last_check = None
        if last_check is not None and now < last_check - timedelta(hours=1):
            return False, "reloj"
    return True, ""


def check_license() -> bool:
    w = _load_file_blob()
    if not w:
        return False
    try:
        data = _merge_payload_state(w)
        now = _trusted_now_with_grace(w)
    except Exception as e:
        write_log(f"check_license: {e}", "WARNING")
        return False
    ok, _tag = _validate_core(data, now)
    if not ok:
        return False
    try:
        dt_anchor = get_trusted_time()
    except Exception:
        dt_anchor = now
    st = dict(w.get("state") or {})
    st["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
    st["ntp_iso"] = dt_anchor.isoformat(timespec="seconds")
    st["ntp_wall"] = time.time()
    w["state"] = st
    ok, _ = _save_file_blob(w)
    return ok


def get_license_failure_message() -> str:
    path = _license_path()
    if not path.is_file():
        return (
            "No hay licencia activa en este equipo.\n\n"
            "Activa el programa con la clave que te envió el autor. "
            f"Máximo {LICENSE_MAX_VALIDITY_DAYS} días por clave."
        )
    w = _load_file_blob()
    if w is None:
        return (
            "No se pudo leer license.dat (archivo dañado, copiado de otro usuario/sistema "
            "o DPAPI no puede descifrarlo en esta sesión)."
        )
    try:
        data = _merge_payload_state(w)
    except Exception as e:
        err = str(e).lower()
        if "firma" in err or "signature" in err or "invalid" in err:
            return "Formato de licencia inválido o firma RSA incorrecta."
        return f"No se pudo interpretar la licencia: {e}"

    try:
        now = _trusted_now_with_grace(w)
    except Exception as e:
        return (
            "No se pudo validar la hora de confianza (NTP).\n\n"
            f"Detalle: {e}\n\n"
            "Conecta a Internet o espera dentro del periodo de gracia si ya hubo un sync NTP previo."
        )

    ok, tag = _validate_core(data, now)
    if ok:
        return ""
    if tag == "hwid":
        return (
            "Esta licencia está asociada a otro equipo (HWID incorrecto).\n\n"
            "Solicita una clave generada para el ID de hardware que muestra abajo."
        )
    if tag == "caducada":
        return "La licencia ha caducado. Solicita una nueva clave al autor."
    if tag == "reloj":
        return "El reloj del sistema parece haber retrocedido respecto al último control. Corrige la hora o reactiva con NTP."
    return "La licencia no es válida en este momento."


def get_license_days_left() -> int | None:
    w = _load_file_blob()
    if not w:
        return None
    try:
        data = _merge_payload_state(w)
        expire_d = datetime.strptime(str(data["expire"]), "%Y-%m-%d").date()
        now = _trusted_now_with_grace(w)
        return (expire_d - now.date()).days
    except Exception:
        return None


def activate_license_from_key(license_key: str) -> tuple[bool, str]:
    raw = license_key.strip().replace(" ", "").replace("\n", "").replace("\r", "")
    hwid = get_hardware_id()
    for variant in (raw, raw.replace("-", "")):
        try:
            inner = base64.b64decode(variant.encode("ascii"))
            doc = json.loads(inner.decode("utf-8"))
            payload = verify_rsa_document(doc)
        except Exception:
            continue
        lic_hwid = str(payload.get("hwid", "")).strip().upper()
        if lic_hwid != hwid:
            write_log(
                f"Activación fallida: HWID distinto (clave para {lic_hwid[:8]}…, equipo {hwid[:8]}…)",
                "WARNING",
            )
            return False, "La licencia no corresponde al HWID de este equipo."
        try:
            expire_d = datetime.strptime(str(payload["expire"]), "%Y-%m-%d").date()
        except Exception:
            write_log("Activación fallida: expire inválido", "WARNING")
            return False, "Fecha de expiración inválida en la licencia."
        try:
            now = refresh_trusted_time_anchor()
        except Exception as e:
            write_log(f"Activación fallida: NTP {e}", "WARNING")
            return False, f"No se pudo obtener hora NTP para activar: {e}"
        today = now.date()
        if today > expire_d:
            write_log("Activación fallida: licencia ya caducada", "WARNING")
            return False, "La licencia ya está caducada."
        span = (expire_d - today).days
        if span > LICENSE_MAX_VALIDITY_DAYS:
            write_log(f"Activación fallida: validez {span} > máximo", "WARNING")
            return False, f"La licencia supera el máximo de {LICENSE_MAX_VALIDITY_DAYS} días."
        rsa_document = {"payload": dict(payload), "signature": doc["signature"]}
        st = {
            "last_check": now.strftime("%Y-%m-%d %H:%M:%S"),
            "ntp_iso": now.isoformat(timespec="seconds"),
            "ntp_wall": time.time(),
        }
        wrapper = {"rsa_document": rsa_document, "state": st}
        saved, save_err = _save_file_blob(wrapper)
        if saved:
            write_log("Activación de licencia correcta", "INFO")
            return True, ""
        write_log(f"Activación fallida: guardar archivo: {save_err}", "WARNING")
        return (
            False,
            "No se pudo guardar la licencia."
            + (f"\n\nDetalle: {save_err}" if save_err else ""),
        )
    write_log("Activación fallida: Base64/JSON inválido", "WARNING")
    return False, "No se pudo leer la clave (Base64 o JSON inválido)."


def save_license(license_key: str) -> bool:
    ok, _ = activate_license_from_key(license_key)
    return ok


def license_status_color_days(days: int | None) -> tuple[str, str]:
    if days is None:
        return "#6b7280", "neutral"
    if days > 7:
        return "#22c55e", "ok"
    if days > 0:
        return "#f59e0b", "warn"
    return "#ef4444", "expired"
