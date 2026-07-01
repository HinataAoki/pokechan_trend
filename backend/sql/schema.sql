-- Pokemon Champions usage forecast calendar - Supabase schema
-- Run this once in the Supabase SQL editor (or via `supabase db push`).

-- ==========================================================
-- Private tables: written only by the backend (service_role).
-- RLS is enabled with no policy for anon/authenticated, so the
-- public anon key cannot read or write these tables at all.
-- ==========================================================

create table if not exists channels (
    channel_id text primary key,
    channel_name text not null,
    subscriber_count bigint not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists videos (
    video_id text primary key,
    youtube_url text not null,
    title text not null,
    published_at timestamptz not null,
    channel_id text not null references channels(channel_id),
    discovered_via text not null check (discovered_via in ('title_keyword', 'hashtag', 'tag', 'game_title')),
    duration_seconds int,
    created_at timestamptz not null default now()
);

-- Migration: widen the check constraint if this table already existed
-- with the older, narrower list of allowed discovered_via values.
alter table videos drop constraint if exists videos_discovered_via_check;
alter table videos add constraint videos_discovered_via_check
    check (discovered_via in ('title_keyword', 'hashtag', 'tag', 'game_title'));

-- Migration: add duration_seconds if this table already existed without it.
alter table videos add column if not exists duration_seconds int;

create index if not exists idx_videos_published_at on videos(published_at);

create table if not exists video_pokemon (
    video_id text not null references videos(video_id) on delete cascade,
    pokemon_name text not null,
    primary key (video_id, pokemon_name)
);

create index if not exists idx_video_pokemon_pokemon_name on video_pokemon(pokemon_name);

create table if not exists view_snapshots (
    id bigint generated always as identity primary key,
    video_id text not null references videos(video_id) on delete cascade,
    hours_offset int not null check (hours_offset in (24, 48, 72, 96, 108, 120, 144)),
    captured_at timestamptz not null default now(),
    view_count bigint not null,
    unique (video_id, hours_offset)
);

alter table channels enable row level security;
alter table videos enable row level security;
alter table video_pokemon enable row level security;
alter table view_snapshots enable row level security;
-- No policies created for these tables: only service_role (which bypasses
-- RLS) can read/write them. anon/authenticated get zero access.

-- ==========================================================
-- Public table: aggregated forecast only. Populated by the
-- backend's forecaster job via upsert (service_role). The
-- anon key is allowed SELECT only, nothing else.
-- ==========================================================

create table if not exists pokemon_daily_forecast (
    date date not null,
    pokemon_name text not null,
    score numeric not null,
    updated_at timestamptz not null default now(),
    primary key (date, pokemon_name)
);

create index if not exists idx_forecast_pokemon_name on pokemon_daily_forecast(pokemon_name);

alter table pokemon_daily_forecast enable row level security;

drop policy if exists "public read forecast" on pokemon_daily_forecast;
create policy "public read forecast"
    on pokemon_daily_forecast
    for select
    to anon
    using (true);

-- No insert/update/delete policy for anon -> only service_role can write.

-- ==========================================================
-- Public table: which videos contributed to a given date/pokemon
-- score, so the frontend can show "influential videos" when a
-- calendar day is tapped. Only video-identifying fields needed for
-- display are exposed here (title/url/published_at/contribution) -
-- the raw videos/channels tables above remain fully private.
-- ==========================================================

create table if not exists pokemon_video_contribution (
    date date not null,
    pokemon_name text not null,
    video_id text not null,
    video_title text not null,
    youtube_url text not null,
    published_at timestamptz not null,
    contribution_score numeric not null,
    primary key (date, pokemon_name, video_id)
);

create index if not exists idx_contribution_date_pokemon
    on pokemon_video_contribution(date, pokemon_name);

alter table pokemon_video_contribution enable row level security;

drop policy if exists "public read contribution" on pokemon_video_contribution;
create policy "public read contribution"
    on pokemon_video_contribution
    for select
    to anon
    using (true);

-- ==========================================================
-- Public table + storage bucket: cached Pokemon icon images.
-- Images are scraped once from an external source and re-hosted here
-- so the frontend never hotlinks a third-party site. Populated by
-- backend/pokemon_images.py (service_role writes, anon SELECT-only).
-- ==========================================================

insert into storage.buckets (id, name, public)
values ('pokemon-icons', 'pokemon-icons', true)
on conflict (id) do nothing;

create table if not exists pokemon_images (
    pokemon_name text primary key,
    image_url text not null,
    fetched_at timestamptz not null default now()
);

alter table pokemon_images enable row level security;

drop policy if exists "public read pokemon images" on pokemon_images;
create policy "public read pokemon images"
    on pokemon_images
    for select
    to anon
    using (true);
