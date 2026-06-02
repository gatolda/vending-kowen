import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// ============================================
// CONFIG (valores públicos — seguros de exponer)
// ============================================
const SUPABASE_URL = 'https://pazkqjyzkrxxkephmvhd.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_Cg2LnmdYwzCjxaZN2HG00w_yLf7z2tX';  // pública (segura de exponer)

const sb = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

// machine_id viene del QR: .../?m=kowen-01
const params = new URLSearchParams(location.search);
const MACHINE_ID = params.get('m');

const $ = (id) => document.getElementById(id);
const show = (id) => { $(id).style.display = ''; };
const hide = (id) => { $(id).style.display = 'none'; };

// ============================================
// ARRANQUE
// ============================================
init();

async function init() {
  const { data: { session } } = await sb.auth.getSession();
  if (session) {
    await showHome(session);
  } else {
    showLogin();
  }
  // Si el login por enlace/Google vuelve con sesión, refrescar
  sb.auth.onAuthStateChange((_evt, session) => {
    if (session) showHome(session);
  });
}

// ============================================
// LOGIN
// ============================================
function showLogin() {
  hide('loading'); hide('home'); show('login');
  hide('logout-btn');
  if (MACHINE_ID) $('login-machine').textContent = `Máquina: ${MACHINE_ID}`;

  $('google-btn').onclick = async () => {
    await sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: location.href },
    });
  };

  $('email-btn').onclick = async () => {
    const email = $('email').value.trim();
    if (!email) { setMsg('login-msg', 'Escribí tu email.', 'err'); return; }
    $('email-btn').disabled = true;
    const { error } = await sb.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: location.href },
    });
    $('email-btn').disabled = false;
    if (error) { setMsg('login-msg', error.message, 'err'); return; }
    setMsg('login-msg', '✉️ Te enviamos un enlace. Revisá tu email.', 'ok');
  };
}

// ============================================
// HOME (logueado)
// ============================================
async function showHome(session) {
  hide('loading'); hide('login'); show('home'); show('logout-btn');
  $('logout-btn').onclick = async () => { await sb.auth.signOut(); location.reload(); };

  const user = session.user;
  $('user-name').textContent = user.email || '👋';

  await loadProfile(user);

  // Máquina (del QR)
  if (MACHINE_ID) {
    show('machine-card'); hide('no-machine');
    $('machine-name').textContent = MACHINE_ID;
    $('redeem-btn').onclick = () => redeem(session);
  } else {
    hide('machine-card'); show('no-machine');
  }

  $('promo-btn').onclick = () => redeemCode(session);

  // Botones de carga de saldo
  document.querySelectorAll('.amt-btn').forEach(b => {
    b.onclick = () => topup(parseInt(b.dataset.amount, 10), session);
  });

  await refreshCredits(user.id);
  await refreshWallet(user.id);
  await refreshHistory();

  // Volvió del checkout de MercadoPago
  if (params.get('pago') === 'ok') {
    setMsg('topup-msg', '✅ Pago recibido. Actualizando saldo…', 'ok');
    setTimeout(() => refreshWallet(user.id), 3000);
    setTimeout(() => refreshWallet(user.id), 8000);
  } else if (params.get('pago') === 'error') {
    setMsg('topup-msg', 'El pago no se completó.', 'err');
  }
}

async function refreshWallet(userId) {
  const { data } = await sb.from('wallet_movements').select('amount_clp');
  const saldo = (data || []).reduce((s, m) => s + m.amount_clp, 0);
  $('saldo').textContent = '$' + saldo.toLocaleString('es-CL');
}

async function topup(amount, session) {
  setMsg('topup-msg', 'Redirigiendo a MercadoPago…', '');
  try {
    const res = await fetch('/api/topup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}` },
      body: JSON.stringify({ amount }),
    });
    const data = await res.json();
    if (!res.ok || !data.init_point) { setMsg('topup-msg', data.error || 'No se pudo iniciar el pago.', 'err'); return; }
    location.href = data.init_point;   // ir al checkout de MercadoPago
  } catch (e) {
    setMsg('topup-msg', 'Error de red. Intentá de nuevo.', 'err');
  }
}

async function redeemCode(session) {
  const code = $('promo-code').value.trim();
  if (!code) { setMsg('promo-msg', 'Escribí un código.', 'err'); return; }
  $('promo-btn').disabled = true;
  setMsg('promo-msg', 'Validando…', '');
  try {
    const res = await fetch('/api/redeem-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}` },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    $('promo-btn').disabled = false;
    if (!res.ok) { setMsg('promo-msg', data.error || 'No se pudo.', 'err'); return; }
    setMsg('promo-msg', `✅ ¡+${data.granted} recarga(s) gratis!`, 'ok');
    $('promo-code').value = '';
    await refreshCredits(session.user.id);
  } catch (e) {
    $('promo-btn').disabled = false;
    setMsg('promo-msg', 'Error de red. Intentá de nuevo.', 'err');
  }
}

async function loadProfile(user) {
  const { data } = await sb.from('profiles').select('nombre, telefono').eq('id', user.id).maybeSingle();
  if (data?.nombre) $('user-name').textContent = data.nombre;
  if (!data || !data.telefono) {
    // Perfil incompleto → pedir nombre + teléfono
    show('profile-card');
    if (data?.nombre) $('prof-nombre').value = data.nombre;
    $('prof-save').onclick = () => saveProfile(user.id);
  } else {
    hide('profile-card');
  }
}

async function saveProfile(userId) {
  const nombre = $('prof-nombre').value.trim();
  const telefono = $('prof-telefono').value.trim();
  if (!telefono) { setMsg('prof-msg', 'Poné tu teléfono.', 'err'); return; }
  $('prof-save').disabled = true;
  const { error } = await sb.from('profiles').update({ nombre, telefono }).eq('id', userId);
  $('prof-save').disabled = false;
  if (error) { setMsg('prof-msg', error.message, 'err'); return; }
  setMsg('prof-msg', '✅ ¡Gracias!', 'ok');
  if (nombre) $('user-name').textContent = nombre;
  setTimeout(() => hide('profile-card'), 800);
}

async function refreshCredits(userId) {
  const { data, error } = await sb.from('credit_movements').select('delta');
  if (error) { $('credits').textContent = '–'; return; }
  const balance = (data || []).reduce((s, m) => s + m.delta, 0);
  $('credits').textContent = balance;
  $('redeem-btn').disabled = balance < 1 || !MACHINE_ID;
}

async function refreshHistory() {
  const { data } = await sb.from('redemptions')
    .select('machine_id, liters, status, created_at')
    .order('created_at', { ascending: false })
    .limit(10);
  const el = $('history');
  if (!data || !data.length) {
    el.innerHTML = '<p class="muted small">Sin canjes todavía.</p>';
    return;
  }
  el.innerHTML = data.map(r => {
    const fecha = (r.created_at || '').replace('T', ' ').slice(0, 16);
    const cls = r.status === 'done' ? 'badge-done' : r.status === 'error' ? 'badge-error' : 'badge-pending';
    return `<div class="hist-row">
      <span>${fecha} · ${r.machine_id || ''}</span>
      <span class="badge ${cls}">${r.status}</span>
    </div>`;
  }).join('');
}

// ============================================
// CANJE (vía función serverless, que valida y despacha)
// ============================================
async function redeem(session) {
  $('redeem-btn').disabled = true;
  setMsg('redeem-msg', 'Procesando…', '');
  try {
    const res = await fetch('/api/redeem', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ machine_id: MACHINE_ID }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMsg('redeem-msg', data.error || 'No se pudo canjear.', 'err');
      $('redeem-btn').disabled = false;
      return;
    }
    setMsg('redeem-msg', '✅ ¡Recarga en camino! Acercá tu bidón a la máquina.', 'ok');
    await refreshCredits(session.user.id);
    await refreshHistory();
  } catch (e) {
    setMsg('redeem-msg', 'Error de red. Intentá de nuevo.', 'err');
    $('redeem-btn').disabled = false;
  }
}

function setMsg(id, text, cls) {
  const el = $(id);
  el.textContent = text;
  el.className = 'msg' + (cls ? ' ' + cls : '');
}
