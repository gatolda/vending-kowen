#!/bin/bash
# Setea/rota la SECRET KEY de Supabase en el .env del dashboard, de forma segura.
# Patrón: input silencioso → validación → backup → replace → restart service.
# (Basado en el patrón de rotación de secretos del equipo.)
set -euo pipefail

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════
VAR_NAME="SUPABASE_SERVICE_KEY"
ENV_FILE="$HOME/vending-kowen/apps/dashboard/.env"
EXAMPLE_FILE="$HOME/vending-kowen/apps/dashboard/.env.example"
VALIDATE_REGEX='^.{20,}$'                          # min 20 chars
SERVICES_TO_RESTART=("kowen-dashboard.service")
# ═══════════════════════════════════════════

BACKUP="/tmp/.env.bak.$$"
trap 'rm -f "$BACKUP"' EXIT

# Si no existe el .env, crearlo desde el ejemplo (trae URL + MACHINE_ID no secretos)
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$EXAMPLE_FILE" ]]; then
        cp "$EXAMPLE_FILE" "$ENV_FILE"
        echo "ℹ️  Creado $ENV_FILE desde .env.example (revisá URL y MACHINE_ID)"
    else
        touch "$ENV_FILE"
    fi
    chmod 600 "$ENV_FILE"
fi

echo "Pegá tu ${VAR_NAME} (sb_secret_...) y presioná Enter:"
echo "(no vas a ver lo que tipeás — es a propósito)"
read -rs SECRET
echo

# Validación
if [[ ! "$SECRET" =~ $VALIDATE_REGEX ]]; then
    echo "❌ Valor no parece válido (largo: ${#SECRET})."
    unset SECRET
    exit 1
fi

# Backup + replace atómico de la línea
cp "$ENV_FILE" "$BACKUP"
sed -i "/^${VAR_NAME}=/d" "$ENV_FILE"          # borra línea vieja si existe
printf '%s=%s\n' "$VAR_NAME" "$SECRET" >> "$ENV_FILE"
unset SECRET                                    # saca el secret de la memoria del shell
chmod 600 "$ENV_FILE"

echo "✅ ${VAR_NAME} actualizado en $ENV_FILE"

# Restart services
for svc in "${SERVICES_TO_RESTART[@]}"; do
    sudo systemctl restart "$svc" && echo "✅ ${svc} reiniciado"
done
echo "   (backup temporal eliminado de /tmp)"
echo
echo "Verificá el sync con:  journalctl -u kowen-dashboard -n 20"
echo "Buscá: 'Sync a Supabase activo'"
