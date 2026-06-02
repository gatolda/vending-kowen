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
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
as $$
begin
  insert into profiles (id, telefono) values (new.id, new.phone);
  insert into credit_movements (user_id, delta, reason)
    values (new.id, 1, 'welcome');   -- 1 recarga gratis de bienvenida (ajustable)
  return new;
end;
$$;

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
