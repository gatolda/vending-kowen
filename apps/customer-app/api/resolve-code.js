// Función serverless (Vercel) — resuelve un código numérico de máquina a su id.
// Permite seleccionar la máquina sin escanear el QR (fallback).
//
// GET /api/resolve-code?code=1001  →  { id, nombre }
// Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

export default async function handler(req, res) {
  const code = ((req.query && req.query.code) || '').trim();
  if (!code) return res.status(400).json({ error: 'Falta el código' });
  try {
    const { data } = await sb.from('machines').select('id, nombre').eq('code', code).limit(1);
    if (!data || !data.length) return res.status(404).json({ error: 'Código no encontrado' });
    return res.status(200).json({ id: data[0].id, nombre: data[0].nombre });
  } catch (e) {
    return res.status(500).json({ error: 'Error: ' + (e.message || e) });
  }
}
