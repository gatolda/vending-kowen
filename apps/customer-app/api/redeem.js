// Función serverless (Vercel) — canjea una recarga gratis de forma segura.
// Corre del lado servidor: acá vive la SECRET KEY (en variables de entorno de Vercel),
// nunca en el navegador. Valida sesión + crédito antes de insertar el comando.
//
// Variables de entorno requeridas en Vercel:
//   SUPABASE_URL
//   SUPABASE_SERVICE_KEY        (sb_secret_...)
//   FREE_RECHARGE_SECONDS       (default 10; tiempo del despacho mientras no hay caudalímetro)
//   FREE_RECHARGE_LITERS        (default 20; litros que representa la recarga, para el registro)

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
const FREE_SECONDS = parseInt(process.env.FREE_RECHARGE_SECONDS || '10', 10);
const FREE_LITERS = parseFloat(process.env.FREE_RECHARGE_LITERS || '20');

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });

  // 1) Verificar sesión (JWT en el header Authorization)
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'No autenticado' });

  const { data: userData, error: userErr } = await sb.auth.getUser(token);
  if (userErr || !userData?.user) return res.status(401).json({ error: 'Sesión inválida' });
  const user = userData.user;

  // 2) Validar máquina
  const machineId = (req.body && req.body.machine_id) || null;
  if (!machineId) return res.status(400).json({ error: 'Falta la máquina (escaneá el QR)' });

  try {
    // 3) Saldo de créditos del usuario
    const { data: movs, error: movErr } = await sb
      .from('credit_movements').select('delta').eq('user_id', user.id);
    if (movErr) throw movErr;
    const balance = (movs || []).reduce((s, m) => s + m.delta, 0);
    if (balance < 1) return res.status(400).json({ error: 'No te quedan recargas gratis' });

    // 4) Insertar el comando de despacho en la cola (la Pi lo ejecuta)
    const { data: cmd, error: cmdErr } = await sb
      .from('commands')
      .insert({ machine_id: machineId, command: 'fill', args: { seconds: FREE_SECONDS, liters: FREE_LITERS } })
      .select('id').single();
    if (cmdErr) throw cmdErr;

    // 5) Registrar el canje
    const { data: redem, error: redErr } = await sb
      .from('redemptions')
      .insert({ user_id: user.id, machine_id: machineId, liters: FREE_LITERS, command_id: cmd.id, status: 'pending' })
      .select('id').single();
    if (redErr) throw redErr;

    // 6) Descontar 1 crédito (ledger)
    const { error: decErr } = await sb
      .from('credit_movements')
      .insert({ user_id: user.id, delta: -1, reason: 'redeem', ref: String(redem.id) });
    if (decErr) throw decErr;

    return res.status(200).json({ ok: true, remaining: balance - 1, redemption_id: redem.id });
  } catch (e) {
    return res.status(500).json({ error: 'Error procesando el canje: ' + (e.message || e) });
  }
}
