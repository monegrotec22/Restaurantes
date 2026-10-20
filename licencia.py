# -*- coding: utf-8 -*-
"""
MOTOR DE LICENCIAS - PERLA RESTAURANTES
Licencias offline por equipo, con firma HMAC.
Plazos: 24 horas, 1 mes (30 dias), 6 meses (180 dias), 1 ano (365 dias), permanente.
"""
import os, sys, json, time, hmac, hashlib, uuid, socket, datetime

SECRETO = b"PERLA-RESTAURANTES-LIC-SECRETO-2026-v1"
ARCHIVO_LICENCIA = "licencia.key"

DURACIONES = {
    "24h":  ("24 horas",        1),
    "1m":   ("1 mes (30 dias)", 30),
    "6m":   ("6 meses (180)",   180),
    "1a":   ("1 ano (365)",     365),
    "perm": ("Permanente",      None),
}

def _hex8(s):
    return hashlib.md5(s.encode()).hexdigest()[:8].upper()

def id_maquina():
    """Identificador unico del equipo (MAC + hostname).
    En la nube (Render/PythonAnywhere/etc.) la MAC cambia en cada
    redeploy. Para fijar el ID y que la licencia no se invalide,
    defina la variable de entorno PERLA_MACHINE_ID con 8 caracteres
    hex (ej: A1B2C3D4), o use una licencia wildcard ('*')."""
    env_id = os.environ.get("PERLA_MACHINE_ID", "").strip().upper()
    if env_id:
        return env_id[:8].ljust(8, "0")
    try:
        mac = uuid.getnode()
    except Exception:
        mac = 0
    return _hex8("%s|%s|%s" % (mac, socket.gethostname(), sys.platform))

def _ruta_archivo():
    # DATA_DIR se define en app.py; si se importa solo, usar carpeta local
    base = os.environ.get("PERLA_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, ARCHIVO_LICENCIA)

def _firmar(payload):
    return hmac.new(SECRETO, payload.encode(), hashlib.sha256).hexdigest()[:16].upper()

def generar_clave(id_maq, duracion):
    """Genera una clave de licencia. id_maq='*' para cualquier equipo."""
    if duracion not in DURACIONES:
        raise ValueError("Duracion invalida: %s" % duracion)
    nombre, dias = DURACIONES[duracion]
    if dias is None:
        exp_ts = 0  # 0 = permanente
    else:
        exp_ts = int(time.time()) + dias * 86400
    mid = "00000000" if id_maq == "*" else id_maq.strip().upper()[:8]
    payload = "%08X%s" % (exp_ts, mid)
    sig = _firmar(payload)
    raw = payload + sig  # 8+8+16 = 32 hex
    grupos = [raw[i:i+4] for i in range(0, 32, 4)]
    return "PR-" + "-".join(grupos)

def validar_clave(clave):
    """Valida una clave. Devuelve (ok, dias_restantes, permanente, mensaje)."""
    try:
        c = clave.strip().upper().replace(" ", "")
        if not c.startswith("PR-"):
            return False, 0, False, "Formato de clave invalido."
        raw = c[3:].replace("-", "")
        if len(raw) != 32:
            return False, 0, False, "Clave incompleta."
        exp_hex, mid, sig = raw[0:8], raw[8:16], raw[16:32]
        exp_ts = int(exp_hex, 16)
        payload = "%08X%s" % (exp_ts, mid)
        if _firmar(payload) != sig:
            return False, 0, False, "Firma de clave invalida (clave alterada)."
        if mid != "00000000" and mid != id_maquina():
            return False, 0, False, "Esta licencia es para otro equipo."
        if exp_ts == 0:
            return True, 999999, True, "Licencia permanente activa."
        segundos = exp_ts - time.time()
        if segundos < 0:
            return False, 0, False, "La licencia ha expirado."
        restantes = int(segundos / 86400)
        if restantes <= 0:
            horas = max(1, int(segundos / 3600))
            return True, 0, False, "Licencia activa (~%d hora(s) restantes)." % horas
        return True, restantes, False, "Licencia activa (%d dias restantes)." % restantes
    except Exception as e:
        return False, 0, False, "Error al validar: %s" % e

def guardar(clave):
    with open(_ruta_archivo(), "w", encoding="utf-8") as f:
        f.write(clave.strip())

def cargar():
    p = _ruta_archivo()
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def estado():
    """Devuelve dict con el estado de la licencia actual."""
    clave = cargar()
    if not clave:
        return {"activa": False, "dias": 0, "permanente": False, "mensaje": "Sin licencia activa.", "id_maquina": id_maquina(), "clave": ""}
    ok, dias, perm, msg = validar_clave(clave)
    return {"activa": ok, "dias": dias, "permanente": perm, "mensaje": msg, "id_maquina": id_maquina(), "clave": clave}

def activar_demo_24h():
    """Primer arranque: activa automaticamente 24 horas de prueba."""
    if not cargar():
        clave = generar_clave(id_maquina(), "24h")
        guardar(clave)
        return clave
    return None

if __name__ == "__main__":
    # Modo generador rapido: python licencia.py <id_maquina|*> <duracion>
    if len(sys.argv) >= 3:
        print(generar_clave(sys.argv[1], sys.argv[2]))
    else:
        print("ID de este equipo:", id_maquina())
        print("Estado:", estado())
