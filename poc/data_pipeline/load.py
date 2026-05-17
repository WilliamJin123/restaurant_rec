"""
Upsert enriched + embedded restaurants into Supabase.

Reads from  poc/data_pipeline/data/enriched/<city>/<id>.json
Skips records that haven't been enriched + embedded yet.
Uses INSERT ... ON CONFLICT (google_place_id) so re-runs update in place.

Usage:
    uv run python poc/data_pipeline/load.py
    uv run python poc/data_pipeline/load.py waterloo
"""
import json
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import db

ENRICHED_DIR = config.ROOT / "data" / "enriched"

UPSERT = """
insert into restaurants (
  google_place_id, city, name, formatted_address, lat, lng,
  types, primary_type, price_level, rating, user_rating_count,
  opening_hours, website_uri, phone, photos, raw_reviews,
  tags, best_for, noise_level, service_pace, value_feel, dietary,
  vibe_summary, signature_dishes, embedding,
  raw_fetched_at, enriched_at, embedded_at, updated_at
) values (
  %(google_place_id)s, %(city)s, %(name)s, %(formatted_address)s, %(lat)s, %(lng)s,
  %(types)s, %(primary_type)s, %(price_level)s, %(rating)s, %(user_rating_count)s,
  %(opening_hours)s, %(website_uri)s, %(phone)s, %(photos)s, %(raw_reviews)s,
  %(tags)s, %(best_for)s, %(noise_level)s, %(service_pace)s, %(value_feel)s, %(dietary)s,
  %(vibe_summary)s, %(signature_dishes)s, %(embedding)s,
  now(), now(), now(), now()
)
on conflict (google_place_id) do update set
  city              = excluded.city,
  name              = excluded.name,
  formatted_address = excluded.formatted_address,
  lat               = excluded.lat,
  lng               = excluded.lng,
  types             = excluded.types,
  primary_type      = excluded.primary_type,
  price_level       = excluded.price_level,
  rating            = excluded.rating,
  user_rating_count = excluded.user_rating_count,
  opening_hours     = excluded.opening_hours,
  website_uri       = excluded.website_uri,
  phone             = excluded.phone,
  photos            = excluded.photos,
  raw_reviews       = excluded.raw_reviews,
  tags              = excluded.tags,
  best_for          = excluded.best_for,
  noise_level       = excluded.noise_level,
  service_pace      = excluded.service_pace,
  value_feel        = excluded.value_feel,
  dietary           = excluded.dietary,
  vibe_summary      = excluded.vibe_summary,
  signature_dishes  = excluded.signature_dishes,
  embedding         = excluded.embedding,
  enriched_at       = now(),
  embedded_at       = now(),
  updated_at        = now();
"""

# Google's new Places API returns price as a string enum; map to 0-4.
PRICE_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def to_params(city: str, rec: dict) -> dict:
    enr = rec.get("enrichment", {}) or {}
    loc = rec.get("location", {}) or {}
    photos = [p.get("name") for p in (rec.get("photos") or [])]
    reviews = rec.get("reviews") or []

    return {
        "google_place_id":   rec["id"],
        "city":              city,
        "name":              (rec.get("displayName") or {}).get("text"),
        "formatted_address": rec.get("formattedAddress"),
        "lat":               loc.get("latitude"),
        "lng":               loc.get("longitude"),
        "types":             rec.get("types") or [],
        "primary_type":      rec.get("primaryType"),
        "price_level":       PRICE_MAP.get(rec.get("priceLevel")),
        "rating":            rec.get("rating"),
        "user_rating_count": rec.get("userRatingCount"),
        "opening_hours":     json.dumps(rec["regularOpeningHours"]) if rec.get("regularOpeningHours") else None,
        "website_uri":       rec.get("websiteUri"),
        "phone":             rec.get("nationalPhoneNumber"),
        "photos":            json.dumps(photos) if photos else None,
        "raw_reviews":       json.dumps(reviews) if reviews else None,
        "tags":              enr.get("tags") or [],
        "best_for":          enr.get("best_for") or [],
        "noise_level":       enr.get("noise_level"),
        "service_pace":      enr.get("service_pace"),
        "value_feel":        enr.get("value_feel"),
        "dietary":           enr.get("dietary") or [],
        "vibe_summary":      enr.get("vibe_summary"),
        "signature_dishes":  enr.get("signature_dishes") or [],
        "embedding":         np.array(rec["embedding"], dtype=np.float32),
    }


def main() -> None:
    load_dotenv()
    cities = sys.argv[1:] or list(config.CITIES.keys())

    conn = db.connect()
    total, skipped = 0, 0
    with conn:
        with conn.cursor() as cur:
            for city in cities:
                cdir = ENRICHED_DIR / city
                if not cdir.exists():
                    print(f"  ! no enriched dir for {city}")
                    continue
                files = sorted(cdir.glob("*.json"))
                print(f"\n=== LOAD: {city} ({len(files)} files) ===")
                for path in files:
                    rec = json.loads(path.read_text())
                    if "embedding" not in rec or "enrichment" not in rec:
                        skipped += 1
                        continue
                    cur.execute(UPSERT, to_params(city, rec))
                    total += 1

    print(f"\nDone. Upserted {total} restaurants ({skipped} skipped — not yet enriched + embedded).")


if __name__ == "__main__":
    main()
