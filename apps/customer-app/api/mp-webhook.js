// Función serverless (Vercel) — webhook de MercadoPago.
// MP avisa cuando hay novedad de un pago; consultamos el pago y, si está aprobado,
// acreditamos el saldo en la billetera (de forma idempotente).
//
// Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, MP_ACCESS_TOKEN

import { createClient } from '@supabase/supabase-js';

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
const MP_TOKEN = process.env.MP_ACCESS_TOKEN;

export default async function handler(req, res) {
  try {
    const q = req.query || {};
    const body = req.body || {};
    const type = q.type || body.type || q.topic || body.topic;
    const paymentId = q['data.id'] || (body.data && body.data.id) || q.id || body.id;

    // Solo nos interesan notificaciones de pago
    if (type !== 'payment' || !paymentId) return res.status(200).json({ ignored: true });

    // Consultar el pago real en MercadoPago
    const mpRes = await fetch(`https://api.mercadopago.com/v1/payments/${paymentId}`, {
      headers: { 'Authorization': `Bearer ${MP_TOKEN}` },
    });
    const pay = await mpRes.json();
    if (!mpRes.ok) return res.status(200).json({ error: 'no pude leer el pago' });
    if (pay.status !== 'approved') return res.status(200).json({ status: pay.status });

    const ourId = parseInt(pay.external_reference, 10);

    // Idempotencia: aprobar el registro SOLO si seguía pending. Si ya estaba
    // aprobado (reintento del webhook), no acreditamos de nuevo.
    const { data: updated } = await sb.from('payments')
      .update({ status: 'approved', provider_ref: String(paymentId) })
      .eq('id', ourId).eq('status', 'pending')
      .select('user_id, amount_clp');
    if (!updated || !updated.length) return res.status(200).json({ already: true });

    const row = updated[0];
    await sb.from('wallet_movements').insert({
      user_id: row.user_id,
      amount_clp: row.amount_clp,
      reason: 'topup',
      ref: String(paymentId),
    });
    return res.status(200).json({ ok: true });
  } catch (e) {
    // Responder 200 para que MP no reintente infinito por un error nuestro
    console.error('mp-webhook error:', e);
    return res.status(200).json({ error: String(e) });
  }
}
