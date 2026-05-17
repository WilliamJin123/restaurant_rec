from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "raw"

CITIES = {
    "waterloo": {
        "lat": 43.4643,
        "lng": -80.5204,
        "radius_m": 6000,
    },
    "edmonton": {
        "lat": 53.5461,
        "lng": -113.4938,
        "radius_m": 15000,
    },
}

QUERIES = [
    "restaurants",
    "cafes",
    "asian restaurants",
    "italian restaurants",
    "mexican restaurants",
    "indian restaurants",
    "japanese restaurants",
    "chinese restaurants",
    "vietnamese restaurants",
    "thai restaurants",
    "korean restaurants",
    "middle eastern restaurants",
    "pubs",
    "breakfast",
    "brunch",
    "bakeries",
    "dessert",
    "bars",
    "fast food",
    "vegetarian restaurants",
]
