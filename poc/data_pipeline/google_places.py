import os
import time
import requests

BASE = "https://places.googleapis.com/v1"

SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.primaryType,places.types,places.formattedAddress"
)

DETAIL_FIELD_MASK = (
    "id,displayName,formattedAddress,location,types,primaryType,"
    "priceLevel,rating,userRatingCount,regularOpeningHours,"
    "reviews,photos,websiteUri,nationalPhoneNumber"
)


def _key() -> str:
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_PLACES_API_KEY not set — add it to .env or your shell."
        )
    return key


def search_text(query: str, lat: float, lng: float, radius_m: float) -> list[dict]:
    """Run a text search restricted to a circle, paginating to the API max (~60)."""
    headers = {
        "X-Goog-Api-Key": _key(),
        "X-Goog-FieldMask": SEARCH_FIELD_MASK,
        "Content-Type": "application/json",
    }
    body = {
        "textQuery": query,
        "pageSize": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
    }
    out: list[dict] = []
    while True:
        r = requests.post(f"{BASE}/places:searchText", json=body, headers=headers)
        if not r.ok:
            raise RuntimeError(f"searchText {r.status_code}: {r.text}")
        data = r.json()
        out.extend(data.get("places", []))
        token = data.get("nextPageToken")
        if not token:
            break
        body["pageToken"] = token
        time.sleep(2)  # pageToken needs a brief delay before it's valid
    return out


def get_place_details(place_id: str) -> dict:
    headers = {
        "X-Goog-Api-Key": _key(),
        "X-Goog-FieldMask": DETAIL_FIELD_MASK,
    }
    r = requests.get(f"{BASE}/places/{place_id}", headers=headers)
    if not r.ok:
        raise RuntimeError(f"getPlace {place_id} {r.status_code}: {r.text}")
    return r.json()
