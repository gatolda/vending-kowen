"""
Sincronización best-effort a Supabase (telemetría del fleet).

PRINCIPIO: nunca bloquea ni afecta el control local. Si no hay credenciales,
no hay internet, o Supabase no responde, el dashboard y el control siguen
funcionando igual. El cloud es solo para monitoreo/alertas, jamás un punto de falla.

Credenciales por variables de entorno (las pone el operador en la Pi, fuera de git):
    SUPABASE_URL          ej: https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  service_role key (secreta — solo vive en la Pi)
    MACHINE_ID            ej: kowen-01  (default: kowen-01)

Escribe a dos tablas vía la API REST (PostgREST):
    events       (machine_id, level, message)
    heartbeats   (machine_id, tank_full, min_water, pressure_ok, auto_enabled, operation)
"""

import os
import json
import time
import queue
import threading
import urllib.request

# Config — se completa en start() leyendo el entorno (que app.py puebla desde el .env)
SUPABASE_URL = ""
SUPABASE_KEY = ""
MACHINE_ID = "kowen-01"
ENABLED = False

# Cola de escrituras pendientes. Si se llena (sin internet mucho rato), se
# descartan las más nuevas sin romper nada (el log local sigue siendo la verdad).
_q = queue.Queue(maxsize=2000)


def _post(table, payload):
    """POST una fila a una tabla. Lanza excepción si falla (la maneja el worker)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def _worker():
    """Consume la cola y escribe a Supabase. Reintenta unas veces; si no, descarta."""
    while True:
        table, payload = _q.get()
        for attempt in range(3):
            try:
                _post(table, payload)
                break
            except Exception:
                time.sleep(2 * (attempt + 1))  # backoff simple
        _q.task_done()


def start():
    """Lee las credenciales del entorno y arranca el worker. Devuelve True si quedó activo."""
    global SUPABASE_URL, SUPABASE_KEY, MACHINE_ID, ENABLED
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
    MACHINE_ID = os.environ.get("MACHINE_ID", "kowen-01")
    ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)
    if not ENABLED:
        return False
    threading.Thread(target=_worker, daemon=True).start()
    return True


def push_event(level, message):
    """Encola un evento (no bloquea; si la cola está llena, lo descarta)."""
    if not ENABLED:
        return
    try:
        _q.put_nowait(("events", {
            "machine_id": MACHINE_ID,
            "level": level,
            "message": message,
        }))
    except queue.Full:
        pass


def push_heartbeat(state):
    """Encola un heartbeat con el estado actual de la máquina."""
    if not ENABLED:
        return
    payload = {"machine_id": MACHINE_ID}
    payload.update(state)
    try:
        _q.put_nowait(("heartbeats", payload))
    except queue.Full:
        pass
