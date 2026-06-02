// Función serverless (Vercel) — inicia una carga de saldo vía MercadoPago Checkout Pro.
// Crea una preferencia de pago y devuelve el init_point (URL del checkout).
// El webhook /api/mp-webhook acredita el saldo cuando el pago se aprueba.
//
// Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, MP_ACCESS_TOKEN, APP_BASE_URL (opcional)

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
const MP_TOKEN = process.env.MP_ACCESS_TOKEN;
const BASE_URL = (process.env.APP_BASE_URL || 'https://vending-kowen.vercel.app').replace(/\/$/, '');
const AMOUNTS = [2000, 5000, 10000];   // montos permitidos (CLP)

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });

  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'No autenticado' });
  const { data: ud, error: ue } = await sb.auth.getUser(token);
  if (ue || !ud?.user) return res.status(401).json({ error: 'Sesión inválida' });
  const user = ud.user;

  const amount = parseInt((req.body && req.body.amount) || 0, 10);
  if (!AMOUNTS.includes(amount)) return res.status(400).json({ error: 'Monto inválido' });

  try {
    // Registrar el pago pendiente (external_reference = nuestro id)
    const { data: pay, error: pe } = await sb.from('payments')
      .insert({ user_id: user.id, amount_clp: amount, status: 'pending' })
      .select('id').single();
    if (pe) throw pe;

    // Crear la preferencia en MercadoPago
    const pref = {
      items: [{ title: 'Carga de saldo Kowen', quantity: 1, unit_price: amount, currency_id: 'CLP' }],
      external_reference: String(pay.id),
      notification_url: `${BASE_URL}/api/mp-webhook`,
      back_urls: {
        success: `${BASE_URL}/?pago=ok`,
        pending: `${BASE_URL}/?pago=pendiente`,
        failure: `${BASE_URL}/?pago=error`,
      },
      auto_return: 'approved',
      metadata: { user_id: user.id, payment_id: pay.id },
    };
    const mpRes = await fetch('https://api.mercadopago.com/checkout/preferences', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${MP_TOKEN}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(pref),
    });
    const data = await mpRes.json();
    if (!mpRes.ok) return res.status(500).json({ error: 'MercadoPago: ' + (data.message || 'error') });

    await sb.from('payments').update({ provider_ref: data.id }).eq('id', pay.id);
    return res.status(200).json({ init_point: data.init_point });
  } catch (e) {
    return res.status(500).json({ error: 'Error: ' + (e.message || e) });
  }
}
