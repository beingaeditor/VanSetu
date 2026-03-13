#!/usr/bin/env python3
"""
Seed Suggestions — Populate MongoDB with realistic community suggestions.

Usage:
    python scripts/seed_suggestions.py

This script:
1. Boots the backend services to get real corridor data
2. Empties the corridor_suggestions collection
3. Inserts diverse, context-aware dummy suggestions based on each corridor's
   type, severity, and intervention recommendations
"""

import os
import sys
import random
import hashlib
from datetime import datetime, timedelta

# ── Make backend importable ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from app.config import get_settings
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.intervention_service import enrich_geojson_corridors


# ──────────────────────────────────────────────────────────────────────────────
# Suggestion templates — grouped by corridor type
# {name} is replaced with the corridor/road name
# ──────────────────────────────────────────────────────────────────────────────

TEMPLATES = {
    "heat_dominated": [
        "Please plant more shade trees along {name} — it's unbearable to walk here in summer.",
        "Can we get water fountains or mist sprays near the bus stops on {name}?",
        "The footpath on {name} gets extremely hot. Cool pavement or shade structures would help.",
        "My kids walk to school via {name}. Desperately need tree cover for safety from heat.",
        "Why not pilot a cool-roof program for buildings along {name}? Radiant heat is intense.",
        "Suggest installing solar-powered shade sails at major crossings on {name}.",
        "Open-air vendors on {name} suffer from heat strokes every summer. Urgent shade needed.",
        "The elderly in our colony avoid {name} after 10 AM due to heat. Tree canopy please!",
        "Reflective paint on pavement + Neem tree planting along {name} would make a big difference.",
        "Could we get covered pedestrian connectors between metro station and {name} bus stop?",
        "Morning joggers have shifted away from {name} because there's zero shade. Let's fix this.",
        "Request: vertical gardens on the flyover pillars along {name} to reduce radiated heat.",
    ],
    "pollution_dominated": [
        "The air on {name} is terrible during rush hour. Dense hedges could help filter dust.",
        "Can we plant pollution-absorbing species like Arjuna trees along {name}?",
        "Please add green screens on the pedestrian side of {name}. The exhaust is suffocating.",
        "Install real-time AQI boards on {name} so residents know when to wear masks.",
        "Traffic police on {name} need relief. Green buffers between lanes and footpaths please.",
        "My balcony faces {name} and the soot is relentless. Multi-row vegetation buffer would help.",
        "Consider a 3-meter deep hedge wall along the school boundary on {name}.",
        "Construction dust on {name} is out of control. Green mesh barriers + sapling plantation needed.",
        "The PM2.5 spike near {name} flyover is alarming. Can we get a smog tower or green wall?",
        "How about a citizen science air monitoring program along {name}? Would build support for greening.",
        "Heavy trucks on {name} at night kick up dust. Ground-cover plants on verges would bind the soil.",
        "Suggest bamboo screens — fast-growing and great at trapping particulates near {name}.",
    ],
    "green_deficit": [
        "There's literally no greenery on {name}. Even small planters would improve the vibe.",
        "A pocket park somewhere along {name} would give children a safe outdoor space.",
        "Can we convert the unused median on {name} into a flowering native garden?",
        "{name} has wide unused margins. Perfect for a Miyawaki micro-forest patch!",
        "I'd love a weekend farmer's market space with greenery along {name}.",
        "The concrete stretch of {name} is depressing. Climbing plants on walls would soften it.",
        "Please connect the two parks near {name} with a tree-lined walking path.",
        "Community members are willing to adopt tree pits along {name} — we just need govt support.",
        "A cycle track with planters on {name} would promote both health and greenery.",
        "Rooftop garden incentives for buildings on {name} could rapidly increase green cover.",
        "{name} is the greyest corridor in our locality. Any greening effort will be welcome.",
        "Suggest rain gardens along {name}'s storm drains — dual benefit: drainage + greenery.",
    ],
    "mixed_exposure": [
        "{name} has heat, dust, and zero greenery. A comprehensive green corridor plan is needed.",
        "Multi-layered planting on {name}: tall trees for shade, shrubs for dust, ground cover for heat.",
        "Request a pilot 'complete green street' redesign for one block of {name}.",
        "Can {name} be a flagship VanSetu corridor? It has all the problems and high visibility.",
        "The intersection of {name} could be a great place for a small urban food garden.",
        "Community composting + tree planting program along {name} would help on multiple fronts.",
        "Suggest partnering with local schools for a 'Green {name}' adoption campaign.",
        "Stormwater flooding + heat + dust on {name} — bioswales with shade trees address all three.",
        "{name} needs a phased approach: quick wins (potted plants) now, proper tree planting next monsoon.",
        "How about a design competition for reimagining {name} as a green boulevard?",
        "I've seen successful green corridors in Pune. {name} has similar potential — let's do it.",
        "Noise, heat, and pollution on {name} affect our mental health. Green spaces would help enormously.",
    ],
}

# Generic suggestions that work for any corridor
GENERIC_SUGGESTIONS = [
    "Maintain existing trees on {name} — several have been damaged and not replaced.",
    "Please don't remove trees for road widening on {name}. Plan around them.",
    "Involve RWAs in the greening plan for {name}. Community ownership ensures maintenance.",
    "Would be great to have native butterfly-attracting plants along {name}.",
    "Label the trees on {name} with species names — educational and builds appreciation.",
    "Night lighting in green spaces near {name} would make them safer to use.",
    "Drip irrigation for new saplings on {name} — too many die in the first summer.",
    "Can we use treated wastewater from the nearby STP for irrigation on {name}?",
    "Suggest a monthly community cleanup + tree check walk on {name}.",
    "Heritage trees near {name} should be GPS-tagged and protected.",
]

# Fake IP addresses for realistic seeding
FAKE_IPS = [
    "192.168.1.10", "192.168.1.23", "10.0.0.55", "172.16.0.8",
    "192.168.2.101", "10.0.1.42", "172.16.1.200", "192.168.3.77",
    "10.0.2.15", "172.16.2.33", "192.168.4.60", "10.0.3.88",
    "192.168.5.122", "172.16.3.91", "10.0.4.7", "192.168.6.210",
]


def _random_past_datetime(days_back: int = 90) -> str:
    """Generate a random ISO datetime within the last N days."""
    offset = random.randint(0, days_back * 24 * 3600)
    dt = datetime.utcnow() - timedelta(seconds=offset)
    return dt.isoformat()


def _pick_templates(corridor_type: str, road_name: str, count: int) -> list[dict]:
    """
    Pick `count` unique suggestions for a corridor, mixing type-specific
    and generic templates.
    """
    type_pool = TEMPLATES.get(corridor_type, TEMPLATES["mixed_exposure"])

    # Mix: ~70% type-specific, ~30% generic
    n_typed = max(1, int(count * 0.7))
    n_generic = count - n_typed

    typed_picks = random.sample(type_pool, min(n_typed, len(type_pool)))
    generic_picks = random.sample(GENERIC_SUGGESTIONS, min(n_generic, len(GENERIC_SUGGESTIONS)))

    suggestions = []
    for text in typed_picks + generic_picks:
        suggestions.append({
            "text": text.replace("{name}", road_name),
            "upvotes": random.choices(
                [0, 1, 2, 3, 5, 8, 13, 21],
                weights=[10, 15, 20, 20, 15, 10, 7, 3],
                k=1,
            )[0],
            "client_ip": random.choice(FAKE_IPS),
            "created_at": _random_past_datetime(),
        })

    return suggestions


def main():
    print("=" * 60)
    print("🌱 VanSetu — Seed Community Suggestions")
    print("=" * 60)

    # ── 1. Connect to MongoDB ──
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DB", "urban_green_corridors")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[db_name]
    collection = db["corridor_suggestions"]

    print(f"\n✅ Connected to MongoDB: {db_name}/corridor_suggestions")

    # ── 2. Empty existing suggestions ──
    deleted = collection.delete_many({})
    print(f"🗑️  Deleted {deleted.deleted_count} existing suggestions")

    # ── 3. Load corridor data ──
    print("\n📂 Loading raster + road data (this may take a moment)...")
    settings = get_settings()
    raster = RasterService(settings)
    raster.load_data()
    roads = RoadService(settings)
    aqi = AQIService(settings)

    corridors_gdf = roads.detect_corridors(raster, percentile=85, aqi_service=aqi)
    geojson = roads.roads_to_geojson(corridors_gdf)
    enriched = enrich_geojson_corridors(geojson)

    features = enriched.get("features", [])
    print(f"   Found {len(features)} corridor segments")

    # ── 4. Generate suggestions ──
    print("\n📝 Generating suggestions...")

    # Group features by road name to avoid duplicating suggestions per sub-segment
    road_groups: dict[str, dict] = {}
    for f in features:
        p = f.get("properties", {})
        name = p.get("name")
        if not name:
            continue
        if name not in road_groups:
            road_groups[name] = {
                "corridor_type": p.get("corridor_type", "mixed_exposure"),
                "severity_tier": p.get("severity_tier", "high"),
                "priority": p.get("priority_score") or p.get("gdi_mean") or 0.5,
            }

    print(f"   Unique named corridors: {len(road_groups)}")

    all_docs = []
    for road_name, info in road_groups.items():
        # More suggestions for higher-severity corridors
        tier = info["severity_tier"]
        base_count = {"critical": 6, "high": 4, "moderate": 3}.get(tier, 4)
        # Add some randomness: ±1
        count = max(2, base_count + random.randint(-1, 1))

        suggestions = _pick_templates(info["corridor_type"], road_name, count)

        for s in suggestions:
            all_docs.append({
                "corridor_id": road_name,
                **s,
            })

    # Shuffle so insertion order isn't grouped by corridor
    random.shuffle(all_docs)

    # ── 5. Insert into MongoDB ──
    if all_docs:
        collection.insert_many(all_docs)

    # ── 6. Summary ──
    print(f"\n✅ Inserted {len(all_docs)} suggestions across {len(road_groups)} corridors")

    # Show a sample
    print("\n── Sample suggestions ──")
    samples = random.sample(all_docs, min(5, len(all_docs)))
    for s in samples:
        print(f"  [{s['corridor_id']}] ({s['upvotes']}👍) {s['text'][:80]}...")

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
