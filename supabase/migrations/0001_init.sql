-- Restaurant Rec — initial schema
-- Paste into Supabase SQL Editor (Project → SQL Editor → New query → Run)
-- Safe to re-run: every create uses IF NOT EXISTS / OR REPLACE where possible.

create extension if not exists vector;

-- One row per Google place. LLM enrichment + embedding live here.
create table if not exists restaurants (
  id                 uuid primary key default gen_random_uuid(),
  google_place_id    text not null unique,
  city               text not null,
  name               text not null,
  formatted_address  text,
  lat                double precision,
  lng                double precision,
  types              text[],
  primary_type       text,
  price_level        int,
  rating             double precision,
  user_rating_count  int,
  opening_hours      jsonb,
  website_uri        text,
  phone              text,
  photos             jsonb,
  raw_reviews        jsonb,

  -- LLM enrichment (closed-vocab + prose)
  tags               text[],
  best_for           text[],
  noise_level        text,
  service_pace       text,
  value_feel         text,
  dietary            text[],
  vibe_summary       text,
  signature_dishes   text[],

  -- Semantic embedding (BAAI/bge-small-en-v1.5 → 384 dim)
  embedding          vector(384),

  raw_fetched_at     timestamptz,
  enriched_at        timestamptz,
  embedded_at        timestamptz,
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);

create index if not exists restaurants_city_idx       on restaurants (city);
create index if not exists restaurants_tags_idx       on restaurants using gin (tags);
create index if not exists restaurants_best_for_idx   on restaurants using gin (best_for);
create index if not exists restaurants_embedding_idx  on restaurants using hnsw (embedding vector_cosine_ops);

-- Every Like / Pass / Tried / Show-another card action is appended here.
-- Feeds the personal ML re-ranker and the per-session exclude list.
create table if not exists user_ratings (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  restaurant_id  uuid not null references restaurants(id) on delete cascade,
  action         text not null check (action in ('like', 'pass', 'tried', 'show_another')),
  query          text,   -- the query / vibe string that surfaced this card
  reason         text,   -- optional chip: too_far | wrong_vibe | too_expensive | not_in_the_mood | ...
  created_at     timestamptz default now()
);

create index if not exists user_ratings_user_idx       on user_ratings (user_id, created_at desc);
create index if not exists user_ratings_restaurant_idx on user_ratings (restaurant_id);

-- RLS — users only see their own ratings; restaurants are readable by anyone signed in.
alter table user_ratings enable row level security;

drop policy if exists "own ratings" on user_ratings;
create policy "own ratings" on user_ratings
  for all to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

alter table restaurants enable row level security;

drop policy if exists "public read" on restaurants;
create policy "public read" on restaurants
  for select to authenticated using (true);
