"""
Generate embeddings for enriched restaurants using a local sentence-transformer.

Reads + writes  poc/data_pipeline/data/enriched/<city>/<id>.json
Adds an "embedding" field (list[float], length 384) per record.

Idempotent: skips records that already have an embedding.
Model: BAAI/bge-small-en-v1.5 (384 dim, runs via ONNX — no PyTorch).

Usage:
    uv run python poc/data_pipeline/embed.py
    uv run python poc/data_pipeline/embed.py waterloo
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

ENRICHED_DIR = config.ROOT / "data" / "enriched"


def build_embed_text(record: dict) -> str:
    """Concatenate the fields that should drive semantic similarity for vibe matching."""
    enr = record.get("enrichment", {}) or {}
    name = (record.get("displayName") or {}).get("text", "")
    types = ", ".join(record.get("types") or [])
    parts = [
        name,
        types,
        enr.get("vibe_summary", ""),
        "tags: " + ", ".join(enr.get("tags") or []),
        "best for: " + ", ".join(enr.get("best_for") or []),
        "signature dishes: " + ", ".join(enr.get("signature_dishes") or []),
    ]
    return "\n".join(p for p in parts if p.strip())


def main() -> None:
    from fastembed import TextEmbedding

    print("Loading embedding model (BAAI/bge-small-en-v1.5, 384 dim)...")
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    cities = sys.argv[1:] or list(config.CITIES.keys())
    for city in cities:
        cdir = ENRICHED_DIR / city
        if not cdir.exists():
            print(f"  ! no enriched dir for {city} — run enrich first")
            continue

        files = sorted(cdir.glob("*.json"))
        records, paths = [], []
        for path in files:
            data = json.loads(path.read_text())
            if "embedding" in data:
                continue
            records.append(data)
            paths.append(path)

        print(f"\n=== EMBED: {city} ===")
        print(f"  {len(files)} enriched files, {len(records)} to embed")
        if not records:
            continue

        texts = [build_embed_text(r) for r in records]
        embeddings = list(model.embed(texts))  # batched under the hood

        for path, record, emb in zip(paths, records, embeddings):
            record["embedding"] = emb.tolist()
            path.write_text(json.dumps(record, indent=2))

        print(f"  embedded {len(records)} restaurants")

    print("\nDone.")


if __name__ == "__main__":
    main()
