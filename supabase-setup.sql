-- CPA scale · Supabase setup
-- Paste this whole file into the Supabase SQL Editor and press Run.
-- Creates the table the instrument writes to, and locks down who can read it.

create table if not exists public.cpa_responses (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  kind        text not null,          -- 'instrument' or 'expert_review'
  version     text,                   -- e.g. v0.7-pool21
  respondent  text,                   -- reviewer name, or null for anonymous respondents
  payload     jsonb not null          -- the full submission
);

-- Row Level Security on: nothing is allowed unless a policy below says so.
alter table public.cpa_responses enable row level security;

-- The public page may INSERT. That is all it may do.
drop policy if exists "public can submit" on public.cpa_responses;
create policy "public can submit"
  on public.cpa_responses
  for insert
  to anon
  with check (true);

-- Deliberately NO select/update/delete policy for the anon role. The key in the
-- page is public, so anyone can read it out of the page source; without a select
-- policy that key still cannot read a single response back. You read the data in
-- the Supabase dashboard, which uses your own credentials rather than this key.

-- Handy view for reading reviews back.
create or replace view public.cpa_review_summary as
select
  id,
  created_at,
  payload->>'reviewer'       as reviewer,
  payload->>'affiliation'    as affiliation,
  payload->>'reviewer_role'  as role,
  jsonb_array_length(payload->'ratings') as n_items,
  payload
from public.cpa_responses
where kind = 'expert_review'
order by created_at desc;
