-- jobwatch database schema for Supabase.
-- Run it in the Supabase dashboard: SQL Editor -> New query -> paste this file -> Run.
-- It is safe to run again: every statement is idempotent.
--
-- Who can do what:
--   * The bot (GitHub Actions) writes jobs with the SECRET key, which bypasses Row Level Security.
--   * The web app uses the PUBLISHABLE key plus your login. Row Level Security only lets a
--     logged-in user through if their user ID is in private.allowed_users, so even if someone
--     else signs up, they see nothing.

-- ---------------------------------------------------------------------------------------------
-- Allow-list (kept in a schema the web API doesn't expose)

create schema if not exists private;

create table if not exists private.allowed_users (
  user_id uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now()
);

-- Used by every policy below. security definer lets it read private.allowed_users;
-- search_path = '' (with fully qualified names) stops anyone hijacking the lookup.
create or replace function private.is_allowed()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from private.allowed_users where user_id = (select auth.uid())
  );
$$;

grant usage on schema private to authenticated;
grant execute on function private.is_allowed() to authenticated;

-- Lets the web app ask "am I on the allow-list?" so it can show setup help instead of an empty inbox.
create or replace function public.am_i_allowed()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select private.is_allowed();
$$;

revoke execute on function public.am_i_allowed() from public, anon;
grant execute on function public.am_i_allowed() to authenticated;

-- ---------------------------------------------------------------------------------------------
-- Jobs: one row per OnlineJobs.ph listing the bot has seen. Written only by the bot.

create table if not exists public.jobs (
  id text primary key,                    -- OnlineJobs.ph job ID (the number at the end of the URL)
  title text not null,
  url text not null,
  posted_at timestamptz,                  -- UTC; changes when an employer reposts the job
  salary text,                            -- free text as shown on the site, e.g. "$5/hr"
  job_type text,                          -- Full Time / Part Time / Gig / Any
  snippet text not null default '',       -- the (truncated) description shown on the search page
  tags text[] not null default '{}',
  matched_keyword text,                   -- which include keyword matched, or null if filtered out
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists jobs_posted_at_idx on public.jobs (posted_at desc);
create index if not exists jobs_matched_idx on public.jobs (posted_at desc) where matched_keyword is not null;

-- ---------------------------------------------------------------------------------------------
-- Your decisions about a job. Kept separate so the bot's updates never overwrite them.

create table if not exists public.job_actions (
  job_id text primary key references public.jobs (id) on delete cascade,
  status text not null check (status in ('new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'skipped')),
  notes text not null default '',
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------------------------
-- Inbox: jobs joined with your decision. A job with no decision has status 'new'.
-- security_invoker makes the view obey the Row Level Security of the tables underneath.

create or replace view public.inbox with (security_invoker = true) as
select
  j.*,
  coalesce(a.status, 'new') as status,
  coalesce(a.notes, '') as notes,
  a.updated_at as status_updated_at
from public.jobs j
left join public.job_actions a on a.job_id = j.id;

-- ---------------------------------------------------------------------------------------------
-- Row Level Security

alter table public.jobs enable row level security;
alter table public.job_actions enable row level security;
alter table private.allowed_users enable row level security;  -- no policies: dashboard/SQL only

drop policy if exists "allowed users read jobs" on public.jobs;
create policy "allowed users read jobs" on public.jobs
  for select to authenticated using ((select private.is_allowed()));

drop policy if exists "allowed users manage their actions" on public.job_actions;
create policy "allowed users manage their actions" on public.job_actions
  for all to authenticated
  using ((select private.is_allowed()))
  with check ((select private.is_allowed()));

-- ---------------------------------------------------------------------------------------------
-- Privileges: grant only what each role needs (some projects grant everything by default).

revoke all on public.jobs, public.job_actions, public.inbox from anon, authenticated;
grant select on public.jobs, public.inbox to authenticated;
grant select, insert, update, delete on public.job_actions to authenticated;
grant all on public.jobs, public.job_actions to service_role;

-- ---------------------------------------------------------------------------------------------
-- After you log in to the web app for the first time, add yourself to the allow-list.
-- Run this once in the SQL Editor (replace the email with the one you logged in with):
--
--   insert into private.allowed_users (user_id)
--   select id from auth.users where email = 'you@example.com'
--   on conflict do nothing;
