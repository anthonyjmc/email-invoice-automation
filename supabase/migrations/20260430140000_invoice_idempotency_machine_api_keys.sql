-- Idempotency columns on invoices, machine API keys + audit (service_role only).
-- Apply after 20260430120000_invoices_table_and_rls.sql

alter table public.invoices
    add column if not exists invoice_number text,
    add column if not exists source_content_hash text,
    add column if not exists invoice_ref text,
    add column if not exists idempotency_key text;

-- Same file bytes re-uploaded (per user, or global when user_id is null)
create unique index if not exists invoices_user_source_hash_uidx
    on public.invoices (user_id, source_content_hash)
    where source_content_hash is not null and user_id is not null;

create unique index if not exists invoices_legacy_source_hash_uidx
    on public.invoices (source_content_hash)
    where source_content_hash is not null and user_id is null;

-- Same business invoice (vendor + number + date) per user
create unique index if not exists invoices_user_invoice_ref_uidx
    on public.invoices (user_id, invoice_ref)
    where invoice_ref is not null and length(trim(invoice_ref)) > 0 and user_id is not null;

comment on column public.invoices.source_content_hash is 'SHA-256 hex of raw upload bytes; dedupe re-uploads.';
comment on column public.invoices.invoice_ref is 'Normalized vendor|invoice_number|invoice_date for business-level dedupe.';
comment on column public.invoices.idempotency_key is 'Optional client-supplied key for future use.';

-- Machine API keys (plaintext never stored; only SHA-256 hex of full secret)
create table if not exists public.machine_api_keys (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    key_hash text not null,
    scopes text[] not null default '{}',
    created_at timestamptz not null default now(),
    revoked_at timestamptz,
    last_used_at timestamptz
);

create index if not exists machine_api_keys_active_idx
    on public.machine_api_keys (revoked_at)
    where revoked_at is null;

comment on table public.machine_api_keys is 'Integration API keys; manage rows with service_role only. key_hash = sha256(utf8(secret)).';

-- Audit trail for machine routes (API key id or legacy header)
create table if not exists public.machine_api_audit (
    id bigserial primary key,
    api_key_id uuid references public.machine_api_keys (id) on delete set null,
    legacy_auth boolean not null default false,
    route text not null,
    method text not null,
    client_ip text,
    status_code int,
    created_at timestamptz not null default now()
);

create index if not exists machine_api_audit_created_idx
    on public.machine_api_audit (created_at desc);

comment on table public.machine_api_audit is 'Append-only audit for /invoices and /process-mock-email machine auth.';

alter table public.machine_api_keys enable row level security;
alter table public.machine_api_audit enable row level security;

revoke all on public.machine_api_keys from anon, authenticated;
revoke all on public.machine_api_audit from anon, authenticated;

grant select, insert, update, delete on public.machine_api_keys to service_role;
grant select, insert on public.machine_api_audit to service_role;
grant usage, select on sequence public.machine_api_audit_id_seq to service_role;

create unique index if not exists invoices_user_idempotency_uidx
    on public.invoices (user_id, idempotency_key)
    where idempotency_key is not null and length(trim(idempotency_key)) > 0 and user_id is not null;

create unique index if not exists invoices_legacy_idempotency_uidx
    on public.invoices (idempotency_key)
    where idempotency_key is not null and user_id is null;
