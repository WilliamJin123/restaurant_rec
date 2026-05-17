"""
Fetch restaurants for each configured city from Google Places API.

Two phases:
  1. SEARCH  — run text searches, collect unique place_ids
  2. DETAILS — fetch full details for each unseen id, save JSON to disk

Idempotent: skips place_ids whose JSON already exists locally.
Re-runnable: safe to kill and restart.

Usage:
    python ingest.py                 # all configured cities
    python ingest.py waterloo        # one city
    python ingest.py --dry-run       # only search, count what'd be fetched
"""
import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import google_places as gp


def search_phase(city_name: str, city: dict) -> set[str]:
    print(f"\n=== SEARCH: {city_name} ===")
    seen: set[str] = set()
    for q in config.QUERIES:
        full = f"{q} in {city_name.title()}"
        try:
            results = gp.search_text(full, city["lat"], city["lng"], city["radius_m"])
        except Exception as e:
            print(f"  ! {full}: {e}")
            continue
        new = sum(1 for p in results if p["id"] not in seen)
        for p in results:
            seen.add(p["id"])
        print(f"  '{full}' -> {len(results)} results ({new} new, {len(seen)} unique)")
    return seen


def details_phase(city_name: str, place_ids: set[str], dry_run: bool) -> None:
    out_dir = config.DATA_DIR / city_name
    out_dir.mkdir(parents=True, exist_ok=True)

    to_fetch = [pid for pid in place_ids if not (out_dir / f"{pid}.json").exists()]
    cached = len(place_ids) - len(to_fetch)
    print(f"\n=== DETAILS: {city_name} ===")
    print(f"  {len(place_ids)} ids ({cached} cached, {len(to_fetch)} to fetch)")

    if dry_run:
        print(f"  [dry-run] would fetch {len(to_fetch)} details")
        return

    for i, pid in enumerate(to_fetch, 1):
        try:
            detail = gp.get_place_details(pid)
        except Exception as e:
            print(f"  ! {pid}: {e}")
            continue
        (out_dir / f"{pid}.json").write_text(json.dumps(detail, indent=2))
        name = detail.get("displayName", {}).get("text", pid)
        print(f"  [{i:>3}/{len(to_fetch)}] {name}")
        time.sleep(0.05)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cities", nargs="*", help="city names; default = all")
    parser.add_argument("--dry-run", action="store_true",
                        help="only do searches, skip details fetch")
    args = parser.parse_args()

    cities = args.cities or list(config.CITIES.keys())
    unknown = set(cities) - set(config.CITIES)
    if unknown:
        print(f"Unknown city: {', '.join(unknown)}")
        print(f"Configured: {', '.join(config.CITIES)}")
        sys.exit(1)

    for name in cities:
        ids = search_phase(name, config.CITIES[name])
        details_phase(name, ids, args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
