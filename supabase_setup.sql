-- ==========
-- Extensions
-- ==========
create extension if not exists pgcrypto;

-- ======================
-- Streamers (каналы / боты)
-- ======================
create table if not exists public.streamers (
  id uuid primary key default gen_random_uuid(),
  -- В будущем сюда можно привязать Supabase auth.users.id
  auth_user_id uuid unique,
  -- Внешний идентификатор: YouTube channel ID, Telegram user/chat ID и т.п.
  external_channel_id text,
  platform text not null default 'youtube',  -- 'youtube', 'telegram', ...
  display_name text,
  created_at timestamptz default now()
);

create index if not exists idx_streamers_auth_user_id
  on public.streamers(auth_user_id);

create index if not exists idx_streamers_external_channel_id
  on public.streamers(external_channel_id);

-- ==========================
-- Streamer settings (настройки стримера)
-- ==========================
create table if not exists public.streamer_settings (
  id uuid primary key default gen_random_uuid(),
  streamer_id uuid not null
    references public.streamers(id) on delete cascade,
  -- Основной язык интерфейса / ответов
  target_language text default 'en',
  -- Авто-перевод включён?
  auto_translate boolean default true,
  -- Включить/выключить модерацию
  moderation_enabled boolean default false,
  -- Список стоп-слов для модерации
  blocked_words text[],
  -- Общий JSON для гибких будущих настроек
  extra_settings jsonb default '{}'::jsonb,
  updated_at timestamptz default now()
);

create index if not exists idx_streamer_settings_streamer_id
  on public.streamer_settings(streamer_id);

-- ==========================
-- Subscribers (подписчики / зрители)
-- ==========================
create table if not exists public.subscribers (
  id uuid primary key default gen_random_uuid(),
  streamer_id uuid not null
    references public.streamers(id) on delete cascade,
  -- Внешний ID пользователя: YouTube user ID / Telegram user ID
  external_user_id text not null,
  username text,
  display_name text,
  language text,
  is_blocked boolean default false,
  first_seen_at timestamptz default now(),
  last_seen_at timestamptz default now(),
  notes text,
  constraint subscribers_unique_per_streamer
    unique (streamer_id, external_user_id)
);

create index if not exists idx_subscribers_streamer_id
  on public.subscribers(streamer_id);

create index if not exists idx_subscribers_external_user_id
  on public.subscribers(external_user_id);

-- ==========================
-- Messages (существующая таблица)
-- ==========================
-- На всякий случай: если messages ещё не создана, создаём в том же формате, что и в Supabase
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  message_id text not null,
  author text not null,
  content text not null,
  language text,
  "timestamp" double precision,
  platform text
);

-- Добавляем недостающие поля (идемпотентно)
alter table public.messages
  add column if not exists created_at timestamptz default now(),
  add column if not exists streamer_id uuid,
  add column if not exists subscriber_id uuid;

-- Делаем message_id уникальным, чтобы не хранить дубли сообщений
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.messages'::regclass
      and conname = 'messages_message_id_key'
  ) then
    alter table public.messages
      add constraint messages_message_id_key unique (message_id);
  end if;
end $$;

-- Внешние ключи на стримера и подписчика
do $$
begin
  if not exists (
    select 1 from pg_constraint
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
    select 1 from pg_constraint
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

-- Индексы для быстрых выборок
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
-- RLS (Row Level Security) – пока всё открыто, потом ужесточим
-- ==========
alter table public.messages enable row level security;
alter table public.streamers enable row level security;
alter table public.streamer_settings enable row level security;
alter table public.subscribers enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
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
    select 1 from pg_policies
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
    select 1 from pg_policies
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
    select 1 from pg_policies
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

-- (опционально – если хочешь явно выдать права для anon/authenticated,
-- но с RLS это и так контролируется политиками)
grant all on table public.messages to anon, authenticated;
grant all on table public.streamers to anon, authenticated;
grant all on table public.streamer_settings to anon, authenticated;
grant all on table public.subscribers to anon, authenticated;
