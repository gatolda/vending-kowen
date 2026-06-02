-- ============================================================
-- App de clientes Kowen — esquema Fase 1
-- Correr en Supabase (SQL Editor). Requiere que ya existan
-- las tablas `machines` y `commands` (del fleet) y Supabase Auth.
-- ============================================================

-- ── Perfil del cliente (1:1 con auth.users de Supabase Auth) ──
create table profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  telefono    text,
  nombre      text,
  created_at  timestamptz default now()
);

-- ── Códigos de promo que otorgan créditos de recarga gratis ──
create table promo_codes (
  id          bigint generated always as identity primary key,
  code        text unique not null,
  credits     int  not null default 1,     -- recargas gratis que otorga
  max_uses    int,                          -- null = ilimitado
  uses_count  int  not null default 0,
  expires_at  timestamptz,
  active      boolean not null default true,
  created_at  timestamptz default now()
);

-- ── Ledger de créditos (grants y consumos). Saldo = sum(delta) del usuario ──
create table credit_movements (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  delta       int  not null,                -- +otorga / -consume
  reason      text not null,                -- welcome | promo | loyalty | redeem
  ref         text,                          -- código de promo, id de canje, etc.
  created_at  timestamptz default now()
);
create index idx_credit_movements_user on credit_movements(user_id);

-- ── Canjes de recarga (cada despacho gratis disparado desde la app) ──
create table redemptions (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  machine_id  text references machines(id),
  liters      numeric,                       -- litros objetivo de la recarga
  command_id  bigint references commands(id),-- comando insertado en la cola
  status      text not null default 'pending', -- pending | done | error
  created_at  timestamptz default now()
);
create index idx_redemptions_user on redemptions(user_id);

-- ============================================================
-- Trigger: al registrarse un usuario, crear su perfil + regalo de bienvenida
-- ============================================================
-- search_path fijo + tablas calificadas (hardening: evita search_path mutable)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, telefono) values (new.id, new.phone);
  insert into public.credit_movements (user_id, delta, reason)
    values (new.id, 1, 'welcome');   -- 1 recarga gratis de bienvenida (ajustable)
  return new;
end;
$$;

-- El trigger corre la función; nadie debe poder invocarla vía RPC
revoke execute on function public.handle_new_user() from anon, authenticated, public;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- ============================================================
-- RLS: el cliente solo ve LO SUYO. Las escrituras sensibles
-- (otorgar créditos, registrar canjes, validar promos) las hace
-- la Edge Function con service role, que saltea RLS.
-- ============================================================
alter table profiles          enable row level security;
alter table promo_codes       enable row level security;
alter table credit_movements  enable row level security;
alter table redemptions       enable row level security;

-- Perfil propio
create policy "perfil propio - select" on profiles
  for select using (auth.uid() = id);
create policy "perfil propio - update" on profiles
  for update using (auth.uid() = id);

-- Créditos propios (solo lectura; los inserta el server)
create policy "creditos propios - select" on credit_movements
  for select using (auth.uid() = user_id);

-- Canjes propios (solo lectura; los inserta el server)
create policy "canjes propios - select" on redemptions
  for select using (auth.uid() = user_id);

-- promo_codes: sin policies para clientes → solo accesible por service role
-- (la validación del código se hace en la Edge Function).

-- ============================================================
-- Sincronizar estado del canje con el del comando.
-- Cuando la Pi marca el comando done/error, el canje refleja ese estado.
-- ============================================================
create or replace function public.sync_redemption_status()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.redemptions
    set status = new.status
  where command_id = new.id and status is distinct from new.status;
  return new;
end;
$$;

revoke execute on function public.sync_redemption_status() from anon, authenticated, public;

drop trigger if exists on_command_status_change on public.commands;
create trigger on_command_status_change
  after update of status on public.commands
  for each row execute function public.sync_redemption_status();

-- ============================================================
-- Billetera (saldo en CLP). Saldo = sum(amount_clp) del usuario.
-- Carga vía MercadoPago (webhook). Consumo al despachar (cuando haya caudalímetro).
-- ============================================================
create table wallet_movements (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  amount_clp  int  not null,            -- + carga / - consumo
  reason      text not null,            -- topup | charge | refund | bonus
  ref         text,                     -- id de pago MercadoPago, id de canje, etc.
  created_at  timestamptz default now()
);
create index idx_wallet_movements_user on wallet_movements(user_id);

create table payments (
  id           bigint generated always as identity primary key,
  user_id      uuid references auth.users(id) on delete cascade,
  provider     text not null default 'mercadopago',
  provider_ref text,                    -- payment id / preference id
  amount_clp   int  not null,
  status       text not null default 'pending',  -- pending | approved | rejected
  created_at   timestamptz default now()
);
create index idx_payments_user on payments(user_id);
create unique index idx_payments_provider_ref on payments(provider_ref) where provider_ref is not null;

alter table wallet_movements enable row level security;
alter table payments         enable row level security;
create policy "wallet propio - select" on wallet_movements for select using (auth.uid() = user_id);
create policy "pagos propios - select" on payments for select using (auth.uid() = user_id);
