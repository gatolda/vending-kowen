// Función serverless (Vercel) — estado público de una máquina para la app.
// Lee el último heartbeat (la tabla está cerrada al cliente) y expone solo
// lo mínimo: si está online y lista para despachar. Sin datos sensibles.
//
// GET /api/machine-status?m=kowen-01
// Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
const OFFLINE_S = 300;  // sin heartbeat por +5 min = fuera de servicio

export default async function handler(req, res) {
  const m = (req.query && req.query.m) || '';
  if (!m) return res.status(400).json({ error: 'falta máquina' });
  try {
    const { data } = await sb.from('heartbeats')
      .select('ts, pressure_ok')
      .eq('machine_id', m).order('ts', { ascending: false }).limit(1);
    const hb = data && data[0];
    const online = !!(hb && (Date.now() - new Date(hb.ts).getTime()) < OFFLINE_S * 1000);
    return res.status(200).json({
      online,
      ready: !!(online && hb.pressure_ok !== false),
    });
  } catch (e) {
    return res.status(200).json({ online: false, ready: false });
  }
}
