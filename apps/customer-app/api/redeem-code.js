// Función serverless (Vercel) — canjea un código de promo que otorga recargas gratis.
// Valida del lado servidor (con la SECRET KEY): código activo, no vencido, con cupo,
// y que el usuario no lo haya usado antes. Suma créditos al ledger.
//
// Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });

  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'No autenticado' });

  const { data: ud, error: ue } = await sb.auth.getUser(token);
  if (ue || !ud?.user) return res.status(401).json({ error: 'Sesión inválida' });
  const user = ud.user;

  const code = ((req.body && req.body.code) || '').trim();
  if (!code) return res.status(400).json({ error: 'Escribí un código' });

  try {
    // Buscar el código (case-insensitive)
    const { data: promos, error: pe } = await sb
      .from('promo_codes').select('*').ilike('code', code).limit(1);
    if (pe) throw pe;
    const promo = promos && promos[0];
    if (!promo || !promo.active) return res.status(400).json({ error: 'Código inválido' });
    if (promo.expires_at && new Date(promo.expires_at) < new Date())
      return res.status(400).json({ error: 'Código vencido' });
    if (promo.max_uses != null && promo.uses_count >= promo.max_uses)
      return res.status(400).json({ error: 'Código agotado' });

    // ¿Ya lo usó este usuario? (un código por persona)
    const { data: prev } = await sb.from('credit_movements')
      .select('id').eq('user_id', user.id).eq('reason', 'promo').eq('ref', promo.code).limit(1);
    if (prev && prev.length) return res.status(400).json({ error: 'Ya usaste este código' });

    // Otorgar créditos + contar el uso
    const { error: ce } = await sb.from('credit_movements')
      .insert({ user_id: user.id, delta: promo.credits, reason: 'promo', ref: promo.code });
    if (ce) throw ce;
    await sb.from('promo_codes').update({ uses_count: promo.uses_count + 1 }).eq('id', promo.id);

    // Nuevo saldo
    const { data: movs } = await sb.from('credit_movements').select('delta').eq('user_id', user.id);
    const balance = (movs || []).reduce((s, m) => s + m.delta, 0);
    return res.status(200).json({ ok: true, granted: promo.credits, balance });
  } catch (e) {
    return res.status(500).json({ error: 'Error: ' + (e.message || e) });
  }
}
