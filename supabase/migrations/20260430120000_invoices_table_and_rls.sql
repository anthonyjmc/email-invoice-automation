-- Invoices table + RLS (per authenticated user).
-- Apply with: supabase db push   OR   paste into Supabase SQL Editor.
-- After RLS is on: use WEB_AUTH_PROVIDER=supabase + user JWT from the app, or set
-- SUPABASE_SERVICE_ROLE_KEY on the server only (never in the browser) for legacy/admin API.

create table if not exists public.invoices (
    id uuid primary key default gen_random_uuid(),
    vendor text not null default 'Unknown Vendor',
    total double precision,
    currency text default 'USD',
    invoice_date text,
    sender_email text,
    created_at timestamptz not null default now()
);

alter table public.invoices
    add column if not exists user_id uuid references auth.users (id) on delete cascade;

create index if not exists invoices_user_id_idx on public.invoices (user_id);
create index if not exists invoices_created_at_idx on public.invoices (created_at desc);

alter table public.invoices enable row level security;

drop policy if exists "invoices_select_own" on public.invoices;
drop policy if exists "invoices_insert_own" on public.invoices;
drop policy if exists "invoices_update_own" on public.invoices;
drop policy if exists "invoices_delete_own" on public.invoices;

create policy "invoices_select_own"
    on public.invoices
    for select
    to authenticated
    using (user_id = auth.uid());

create policy "invoices_insert_own"
    on public.invoices
    for insert
    to authenticated
    with check (user_id = auth.uid());

create policy "invoices_update_own"
    on public.invoices
    for update
    to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

create policy "invoices_delete_own"
    on public.invoices
    for delete
    to authenticated
    using (user_id = auth.uid());

comment on table public.invoices is 'Invoice rows scoped by user_id for RLS; server service_role bypasses RLS.';
