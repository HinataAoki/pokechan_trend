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
    discovered_via text not null check (discovered_via in ('title_keyword', 'hashtag', 'game_title')),
    created_at timestamptz not null default now()
);

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
