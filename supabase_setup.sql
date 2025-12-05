-- ==========
-- Extensions
-- ==========
create extension if not exists pgcrypto;

-- ======================
-- Streamers (channels / bots)
-- ======================
create table if not exists public.streamers (
  id uuid primary key default gen_random_uuid(),
  -- In the future this can reference supabase auth.users.id
  auth_user_id uuid unique,
  -- Optional: "google", "email", "telegram", etc.
  auth_provider text,
  -- Generic external identifier (used by db.get_or_create_streamer)
  external_id text,
  -- External channel identifier: YouTube channel ID, Telegram chat ID, etc.
  external_channel_id text,
  platform text not null default 'youtube',  -- 'youtube', 'telegram', ...
  display_name text,
  email text,
  created_at timestamptz default now()
);

-- If the table already exists, add missing columns idempotently
alter table public.streamers
  add column if not exists auth_user_id uuid,
  add column if not exists auth_provider text,
  add column if not exists external_id text,
  add column if not exists external_channel_id text,
  add column if not exists platform text not null default 'youtube',
  add column if not exists display_name text,
  add column if not exists email text,
  add column if not exists created_at timestamptz default now();

create index if not exists idx_streamers_auth_user_id
  on public.streamers(auth_user_id);

create index if not exists idx_streamers_external_channel_id
  on public.streamers(external_channel_id);

create index if not exists idx_streamers_external_id_platform
  on public.streamers(external_id, platform);

-- ==========================
-- Streamer settings
-- ==========================
create table if not exists public.streamer_settings (
  id uuid primary key default gen_random_uuid(),
  streamer_id uuid not null
    references public.streamers(id) on delete cascade,
  -- Main language of the streamer / channel
  source_language text default 'ru',
  -- Default UI / answer language
  target_language text default 'ru',
  -- Enable auto-translation?
  auto_translate boolean default true,
  -- Generic JSON for flexible future settings
  settings jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  -- Payment details (per streamer, not hard-coded in code)
  card_number_full text,
  donation_alerts_link text,
  buymeacoffee_link text
);

-- If the table already exists, add missing columns idempotently
alter table public.streamer_settings
  add column if not exists source_language text default 'ru',
  add column if not exists target_language text default 'ru',
  add column if not exists auto_translate boolean default true,
  add column if not exists settings jsonb default '{}'::jsonb,
  add column if not exists created_at timestamptz default now(),
  add column if not exists updated_at timestamptz default now(),
  add column if not exists card_number_full text,
  add column if not exists donation_alerts_link text,
  add column if not exists buymeacoffee_link text;

create index if not exists idx_streamer_settings_streamer_id
  on public.streamer_settings(streamer_id);

-- ==========================
-- Subscribers (viewers / followers)
-- ==========================
create table if not exists public.subscribers (
  id uuid primary key default gen_random_uuid(),
  streamer_id uuid not null
    references public.streamers(id) on delete cascade,
  -- External user ID: YouTube user ID / Telegram user ID, etc.
  external_user_id text not null,
  username text,
  platform text,
  created_at timestamptz default now(),
  constraint subscribers_unique_per_streamer
    unique (streamer_id, external_user_id)
);

-- Add missing columns / defaults if table already exists
alter table public.subscribers
  add column if not exists username text,
  add column if not exists platform text,
  add column if not exists created_at timestamptz default now();

create index if not exists idx_subscribers_streamer_id
  on public.subscribers(streamer_id);

create index if not exists idx_subscribers_external_user_id
  on public.subscribers(external_user_id);

-- ==========================
-- Messages (existing table)
-- ==========================
-- If messages does not exist yet, create it in the same format as Supabase
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  message_id text not null,
  author text not null,
  content text not null,
  language text,
  "timestamp" double precision,
  platform text
);

-- Add missing columns idempotently
alter table public.messages
  add column if not exists created_at timestamptz default now(),
  add column if not exists streamer_id uuid,
  add column if not exists subscriber_id uuid;

-- Make message_id unique so we do not store duplicate messages
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.messages'::regclass
      and conname = 'messages_message_id_key'
  ) then
    alter table public.messages
      add constraint messages_message_id_key unique (message_id);
  end if;
end $$;

-- Foreign keys to streamers and subscribers (idempotent)
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.messages'::regclass
      and conname = 'messages_streamer_id_fkey'
  ) then
    alter table public.messages
      add constraint messages_streamer_id_fkey
      foreign key (streamer_id)
      references public.streamers(id)
      on delete set null;
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.messages'::regclass
      and conname = 'messages_subscriber_id_fkey'
  ) then
    alter table public.messages
      add constraint messages_subscriber_id_fkey
      foreign key (subscriber_id)
      references public.subscribers(id)
      on delete set null;
  end if;
end $$;

-- Indexes for faster queries
create index if not exists idx_messages_timestamp
  on public.messages("timestamp");

create index if not exists idx_messages_author
  on public.messages(author);

create index if not exists idx_messages_language
  on public.messages(language);

create index if not exists idx_messages_streamer_id
  on public.messages(streamer_id);

create index if not exists idx_messages_subscriber_id
  on public.messages(subscriber_id);

-- ==========
-- RLS (Row Level Security) – currently open, can be tightened later
-- ==========
alter table public.messages enable row level security;
alter table public.streamers enable row level security;
alter table public.streamer_settings enable row level security;
alter table public.subscribers enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'messages'
      and policyname = 'Allow all on messages'
  ) then
    create policy "Allow all on messages"
      on public.messages
      for all
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'streamers'
      and policyname = 'Allow all on streamers'
  ) then
    create policy "Allow all on streamers"
      on public.streamers
      for all
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'streamer_settings'
      and policyname = 'Allow all on streamer_settings'
  ) then
    create policy "Allow all on streamer_settings"
      on public.streamer_settings
      for all
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'subscribers'
      and policyname = 'Allow all on subscribers'
  ) then
    create policy "Allow all on subscribers"
      on public.subscribers
      for all
      using (true)
      with check (true);
  end if;
end $$;

-- Optional: explicit grants for anon/authenticated
-- (with RLS, access is controlled by policies above)
grant all on table public.messages to anon, authenticated;
grant all on table public.streamers to anon, authenticated;
grant all on table public.streamer_settings to anon, authenticated;
grant all on table public.subscribers to anon, authenticated;
