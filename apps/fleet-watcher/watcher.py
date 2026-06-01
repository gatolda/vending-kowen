#!/usr/bin/env python3
"""
Fleet watcher — vigila Supabase y manda alertas a Telegram.

Corre en el VPS (NO en la Pi), justamente para poder detectar cuando una
máquina se cae o se queda sin internet (eso una Pi caída no lo puede avisar
de sí misma).

Detecta y alerta:
  - Eventos críticos nuevos (level 'warn' o 'err') en la tabla `events`
  - Máquina OFFLINE: si no llega un heartbeat en OFFLINE_THRESHOLD_S
  - Máquina ONLINE de nuevo (recuperación)

Solo usa librería estándar (no requiere pip install).

Config por entorno (.env junto a este archivo):
  SUPABASE_URL            https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY    secret key (lee con bypass de RLS)
  TELEGRAM_BOT_TOKEN      token del bot (@BotFather)
  TELEGRAM_CHAT_ID        a quién mandar las alertas
  OFFLINE_THRESHOLD_S     seg sin heartbeat = offline (default 300)
  POLL_INTERVAL_S         cada cuánto chequea (default 30)
  ALERT_COOLDOWN_S        no repetir el mismo mensaje antes de esto (default 600)
"""

import os
import json
import time
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta


def _load_dotenv(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
OFFLINE_THRESHOLD = float(os.environ.get("OFFLINE_THRESHOLD_S", "300"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL_S", "30"))
ALERT_COOLDOWN = float(os.environ.get("ALERT_COOLDOWN_S", "600"))

# Máquina a la que se dirigen los comandos de Telegram (mientras hay una sola).
# Para varias máquinas, más adelante el comando puede incluir el id.
DEFAULT_MACHINE_ID = os.environ.get("DEFAULT_MACHINE_ID", "kowen-01")

# Íconos por nivel de evento
LEVEL_ICON = {"err": "🔴", "warn": "🟡", "ok": "🟢", "info": "ℹ️"}

# Eventos NOTABLES: aunque sean nivel 'ok'/'info', queremos que avisen.
# Se matchean por substring del mensaje (editá esta lista para sumar/sacar).
NOTABLE = [
    "Sistema iniciado",        # arranque del dashboard
    "Llenado completado",      # recarga despachada
    "tanque LLENO",            # autollenado completó la producción
    "Modo automático ACTIVADO",
]


def icon_for(level, msg):
    if "Llenado" in msg:
        return "💧"
    if "tanque LLENO" in msg:
        return "✅"
    if "Sistema iniciado" in msg:
        return "🟢"
    if "Modo automático" in msg:
        return "🤖"
    return LEVEL_ICON.get(level, "🔔")


def _sb_get(path):
    """GET a la API REST de Supabase. Devuelve lista de dicts."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url)
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def send_telegram(text):
    """Manda un mensaje al chat configurado. No lanza (loguea y sigue)."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("Telegram error:", e)
        return False


# ============================================
# COMANDOS A LA PI (vía cola en Supabase — la Pi los lee y ejecuta)
# ============================================

def queue_command(machine_id, command, args=None):
    """Inserta un comando en la cola de Supabase. Devuelve el id de la fila (o None)."""
    url = f"{SUPABASE_URL}/rest/v1/commands"
    payload = {"machine_id": machine_id, "command": command, "args": args or {}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=representation")  # para recuperar el id
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.load(r)
            return rows[0]["id"] if rows else None
    except Exception as e:
        print("queue_command error:", e)
        return None


def wait_command_result(cmd_id, timeout=15):
    """Espera hasta que la Pi marque el comando done/error. Devuelve (status, result)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.5)
        try:
            rows = _sb_get(f"commands?id=eq.{cmd_id}&select=status,result")
        except Exception:
            continue
        if rows and rows[0]["status"] != "pending":
            return rows[0]["status"], rows[0].get("result") or ""
    return "pending", "sin confirmación todavía (la máquina puede estar offline)"


def run_command(command, label, args=None):
    """Encola un comando y reporta el resultado a Telegram (en un hilo, para no bloquear)."""
    cmd_id = queue_command(DEFAULT_MACHINE_ID, command, args)
    if cmd_id is None:
        send_telegram(f"⚠️ No pude encolar el comando ({label})")
        return

    def _report():
        status, result = wait_command_result(cmd_id)
        if status == "done":
            send_telegram(f"✅ {label}: {result}")
        elif status == "error":
            send_telegram(f"⚠️ {label}: {result}")
        else:
            send_telegram(f"⏳ {label}: {result}")
    threading.Thread(target=_report, daemon=True).start()


# ============================================
# BOT INTERACTIVO (responde comandos)
# ============================================

def _fmt_bool(v, yes, no, unknown="?"):
    if v is True:
        return yes
    if v is False:
        return no
    return unknown


def build_status_text():
    """Arma el texto de estado del fleet leyendo el último heartbeat de cada máquina."""
    try:
        machines = _sb_get("machines?select=id,nombre")
    except Exception as e:
        return f"No pude leer el estado: {e}"
    if not machines:
        return "No hay máquinas registradas."

    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD)).isoformat()
    cutoff_q = urllib.parse.quote(cutoff, safe="")
    out = ["📊 Estado del fleet"]
    for m in machines:
        mid = m["id"]
        nombre = m.get("nombre", "")
        try:
            recent = _sb_get(f"heartbeats?machine_id=eq.{mid}&ts=gte.{cutoff_q}&select=id&limit=1")
            online = len(recent) > 0
            hb = _sb_get(
                f"heartbeats?machine_id=eq.{mid}"
                f"&select=tank_full,min_water,pressure_ok,auto_enabled,operation,ts"
                f"&order=ts.desc&limit=1"
            )
        except Exception as e:
            out.append(f"\n• {nombre} ({mid}): error leyendo ({e})")
            continue

        out.append(f"\n• {nombre} ({mid}) — {'🟢 online' if online else '🔴 OFFLINE'}")
        if not hb:
            out.append("   sin datos todavía")
            continue
        h = hb[0]
        tanque = _fmt_bool(h.get("tank_full"), "✅ lleno", "🔵 no lleno")
        minimo = _fmt_bool(h.get("min_water"), "con agua", "⚠️ vacío")
        presion = _fmt_bool(h.get("pressure_ok"), "OK", "⚠️ sin presión")
        auto = _fmt_bool(h.get("auto_enabled"), "🤖 ON", "OFF")
        oper = h.get("operation") or "—"
        ts = (h.get("ts") or "").replace("T", " ")[:19]
        out.append(f"   Tanque: {tanque} | Mínimo: {minimo} | Presión: {presion}")
        out.append(f"   Auto: {auto} | Operación: {oper}")
        out.append(f"   Último dato: {ts}")
    return "\n".join(out)


HELP_TEXT = (
    "🤖 Comandos:\n"
    "/status — estado del fleet\n"
    "/llenar <seg> — despachar recarga (ej: /llenar 5)\n"
    "/flush — ciclo de flush\n"
    "/producir — producir agua (llenar tanque)\n"
    "/auto on|off — modo automático\n"
    "/stop — 🛑 parar todo (emergencia)\n"
    "/ayuda — esta ayuda"
)


def handle_command(text):
    parts = text.split()
    cmd = parts[0] if parts else ""

    if cmd in ("/status", "/estado"):
        send_telegram(build_status_text())

    elif cmd in ("/llenar", "/despachar"):
        if len(parts) < 2:
            send_telegram("Uso: /llenar <segundos>  (ej: /llenar 5)")
            return
        try:
            seg = int(float(parts[1]))
        except ValueError:
            send_telegram("Segundos inválidos. Ej: /llenar 5")
            return
        seg = max(1, min(60, seg))  # la Pi también clampea, doble seguro
        send_telegram(f"📨 Enviando: despachar {seg}s…")
        run_command("fill", f"Despacho {seg}s", {"seconds": seg})

    elif cmd == "/flush":
        send_telegram("📨 Enviando: flush…")
        run_command("flush", "Flush")

    elif cmd in ("/producir", "/produce"):
        send_telegram("📨 Enviando: producir…")
        run_command("produce", "Producción")

    elif cmd == "/auto":
        arg = (parts[1] if len(parts) > 1 else "").lower()
        if arg in ("on", "encender", "activar"):
            run_command("auto_on", "Modo auto ON")
        elif arg in ("off", "apagar", "desactivar"):
            run_command("auto_off", "Modo auto OFF")
        else:
            send_telegram("Uso: /auto on  |  /auto off")

    elif cmd == "/stop":
        send_telegram("📨 Enviando STOP…")
        run_command("stop", "🛑 STOP")

    elif cmd in ("/help", "/ayuda", "/start", "/comandos"):
        send_telegram(HELP_TEXT)

    else:
        send_telegram("No entendí 🤔. Probá /ayuda")


def tg_get_updates(offset, timeout=25):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?timeout={timeout}"
    if offset is not None:
        url += f"&offset={offset}"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout + 10) as r:
        return json.load(r)


def command_loop():
    """Escucha comandos por Telegram (long-polling) y responde. Corre en su propio hilo.
    Solo atiende al chat autorizado (TG_CHAT)."""
    offset = None
    while True:
        try:
            resp = tg_get_updates(offset, timeout=25)
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                text = (msg.get("text") or "").strip().lower()
                chat_id = str((msg.get("chat") or {}).get("id", ""))
                if not text or chat_id != str(TG_CHAT):
                    continue  # ignorar vacíos y chats no autorizados
                handle_command(text)
        except Exception as e:
            print("command_loop error:", e)
            time.sleep(5)


def main():
    if not (SUPABASE_URL and SUPABASE_KEY):
        raise SystemExit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY en el .env")
    if not (TG_TOKEN and TG_CHAT):
        raise SystemExit("Faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en el .env")

    # Arrancar desde el último evento actual: no queremos re-alertar el historial
    try:
        latest = _sb_get("events?select=id&order=id.desc&limit=1")
        last_id = latest[0]["id"] if latest else 0
    except Exception as e:
        print("No pude leer events al inicio:", e)
        last_id = 0

    offline = {}      # machine_id -> True si ya avisamos que está offline
    last_alert = {}   # clave -> timestamp del último envío (anti-spam)

    def should_send(key):
        now = time.time()
        if last_alert.get(key, 0) + ALERT_COOLDOWN > now:
            return False
        last_alert[key] = now
        return True

    print(f"Fleet watcher iniciado. Poll cada {POLL_INTERVAL:.0f}s, offline a los {OFFLINE_THRESHOLD:.0f}s.")
    send_telegram("🤖 Fleet watcher iniciado — vigilando máquinas.\nEscribí /status para ver el estado.")

    # Hilo que escucha comandos de Telegram (responde /status, /ayuda)
    threading.Thread(target=command_loop, daemon=True).start()

    while True:
        # ── 1) Eventos nuevos: críticos (warn/err) + notables (ok/info en NOTABLE) ──
        try:
            rows = _sb_get(
                f"events?select=id,machine_id,level,message,ts"
                f"&id=gt.{last_id}&order=id.asc"
            )
            for ev in rows:
                last_id = max(last_id, ev["id"])
                level, msg = ev["level"], ev["message"]
                is_critical = level in ("warn", "err")
                is_notable = any(p in msg for p in NOTABLE)
                if not (is_critical or is_notable):
                    continue  # evento de rutina → ignorar
                # Cooldown solo para críticos (que pueden repetirse como estado).
                # Los notables (recarga, arranque) son discretos → siempre se mandan.
                if is_critical and not is_notable:
                    if not should_send(f"{ev['machine_id']}:{msg}"):
                        continue
                send_telegram(f"{icon_for(level, msg)} [{ev['machine_id']}] {msg}")
        except Exception as e:
            print("Error chequeando eventos:", e)

        # ── 2) Máquinas offline / recuperadas ──
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD)).isoformat()
            cutoff_q = urllib.parse.quote(cutoff, safe="")
            machines = _sb_get("machines?select=id,nombre")
            for m in machines:
                mid = m["id"]
                recent = _sb_get(
                    f"heartbeats?select=id&machine_id=eq.{mid}&ts=gte.{cutoff_q}&limit=1"
                )
                is_online = len(recent) > 0
                if not is_online and not offline.get(mid):
                    offline[mid] = True
                    send_telegram(f"🔴 [{mid}] {m.get('nombre','')} OFFLINE — sin datos hace +{OFFLINE_THRESHOLD/60:.0f} min")
                elif is_online and offline.get(mid):
                    offline[mid] = False
                    send_telegram(f"🟢 [{mid}] {m.get('nombre','')} volvió ONLINE")
        except Exception as e:
            print("Error chequeando heartbeats:", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
