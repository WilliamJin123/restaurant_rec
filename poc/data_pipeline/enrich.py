"""
LLM enrichment: read raw Google Places JSON, extract structured tags + vibe summary via Claude Haiku 4.5.

Reads from  poc/data_pipeline/data/raw/<city>/<id>.json
Writes  to  poc/data_pipeline/data/enriched/<city>/<id>.json

Idempotent: skips files already enriched.
Cost: ~$0.0005 per restaurant. Full 1k pull ≈ $0.50.

Usage:
    uv run python poc/data_pipeline/enrich.py
    uv run python poc/data_pipeline/enrich.py waterloo
"""
import json
import sys
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

ENRICHED_DIR = config.ROOT / "data" / "enriched"

# Closed vocabularies — keep filters meaningful and queryable.
Tag = Literal[
    "cozy", "lively", "casual", "upscale", "romantic", "hip", "dive",
    "family_friendly", "classic", "trendy", "low_lit", "bright", "patio",
    "great_cocktails", "good_wine", "craft_beer", "dessert_destination",
    "great_coffee", "instagrammable",
]
BestFor = Literal[
    "date_night", "solo", "groups", "business", "takeout", "late_night",
    "brunch", "quick_lunch", "special_occasion", "kid_friendly",
]
NoiseLevel = Literal["quiet", "conversational", "loud"]
ServicePace = Literal["fast", "moderate", "slow_paced"]
ValueFeel = Literal["cheap_eats", "good_value", "mid_range", "splurge", "overpriced"]
Dietary = Literal["vegetarian_friendly", "vegan_options", "gluten_free", "halal", "kosher"]


class Enrichment(BaseModel):
    tags: list[Tag] = Field(description="Atmosphere and food-angle tags clearly supported by the reviews.")
    best_for: list[BestFor] = Field(description="Occasions this place suits well based on review evidence.")
    noise_level: NoiseLevel
    service_pace: ServicePace
    value_feel: ValueFeel
    dietary: list[Dietary] = Field(description="Dietary accommodations explicitly mentioned in reviews.")
    vibe_summary: str = Field(description="2-3 sentence prose summary of the place's character, cuisine, and what stands out. Concrete and specific, no marketing language.")
    signature_dishes: list[str] = Field(description="Up to 5 dishes named repeatedly in reviews. Use exact dish names.")


SYSTEM = (
    "You extract structured vibe data for restaurants. Given Google Places metadata and "
    "5 user reviews, you output tags from a fixed vocabulary, atmosphere descriptors, and "
    "a short prose summary capturing the place's actual character.\n\n"
    "Be conservative: only emit tags clearly supported by the reviews. Better to leave a "
    "tag out than guess. If reviews don't discuss noise/service/value, infer the most "
    "neutral plausible value from cuisine type + price level."
)


def build_user_message(place: dict) -> str:
    name = place.get("displayName", {}).get("text", "Unknown")
    types = place.get("types", []) or []
    price = place.get("priceLevel", "unknown")
    rating = place.get("rating", "?")
    n_ratings = place.get("userRatingCount", 0)
    reviews = place.get("reviews", []) or []

    parts = [
        f"NAME: {name}",
        f"GOOGLE TYPES: {', '.join(types)}",
        f"PRICE LEVEL: {price}",
        f"GOOGLE RATING: {rating} ({n_ratings} ratings)",
        "",
        "USER REVIEWS:",
    ]
    for i, r in enumerate(reviews, 1):
        text = (r.get("text") or {}).get("text", "")
        rev_rating = r.get("rating", "?")
        if text:
            parts.append(f"[{i}] (rated {rev_rating}/5) {text}")

    if not reviews:
        parts.append("(no review text available)")

    return "\n".join(parts)


def enrich_one(client: anthropic.Anthropic, place: dict) -> Enrichment:
    msg = client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_user_message(place)}],
        output_format=Enrichment,
    )
    return msg.parsed_output


def main() -> None:
    load_dotenv()
    client = anthropic.Anthropic()

    cities = sys.argv[1:] or list(config.CITIES.keys())
    for city in cities:
        raw_dir = config.DATA_DIR / city
        out_dir = ENRICHED_DIR / city
        out_dir.mkdir(parents=True, exist_ok=True)

        if not raw_dir.exists():
            print(f"  ! no raw data for {city} — run ingest first")
            continue

        raw_files = sorted(raw_dir.glob("*.json"))
        to_enrich = [p for p in raw_files if not (out_dir / p.name).exists()]
        print(f"\n=== ENRICH: {city} ===")
        print(f"  {len(raw_files)} raw files, {len(to_enrich)} to enrich")

        for i, raw_path in enumerate(to_enrich, 1):
            try:
                place = json.loads(raw_path.read_text())
            except Exception as e:
                print(f"  ! {raw_path.name}: bad JSON: {e}")
                continue
            try:
                enrichment = enrich_one(client, place)
            except Exception as e:
                print(f"  ! {raw_path.name}: {e}")
                continue
            merged = {**place, "enrichment": enrichment.model_dump()}
            (out_dir / raw_path.name).write_text(json.dumps(merged, indent=2))
            name = place.get("displayName", {}).get("text", raw_path.stem)
            print(f"  [{i:>3}/{len(to_enrich)}] {name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
