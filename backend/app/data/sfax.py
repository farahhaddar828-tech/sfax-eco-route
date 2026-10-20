"""Static reference data for Grand Sfax.

The authoritative road network is NOT this file: it is the full OpenStreetMap
drive network imported by `scripts/import_osm.py` (every street, not a fixed
list). This module only holds:
  * the radial roads and ring roads used to build a schematic demo graph when
    the OSM file has not been imported yet (tests, CI, offline demos);
  * the municipalities/zones used for grouping and reverse lookup;
  * per-category engineering metadata (owner service, SLA, cost model).

Coordinates are approximate centroids — good enough for zone lookup, not survey data.
"""
from dataclasses import dataclass

SFAX_CENTER = (34.7406, 10.7603)  # Bab Bhar / Médina area

# (name, bearing in degrees from the centre, approx clockwise from north)
RADIAL_ROADS: list[tuple[str, float]] = [
    ("Route de Tunis", 5),
    ("Route de Teniour", 335),
    ("Route de Saltnia", 25),
    ("Route de Mahdia", 50),
    ("Route de Menzel Chaker", 305),
    ("Route de Gremda", 285),
    ("Route de Lafrane", 270),
    ("Route de l'Aïn", 255),
    ("Route de l'Aéroport", 235),
    ("Route de Soukra", 215),
    ("Route de Gabès", 200),
]

# Ring roads cut across every radial at a given distance (km) from the centre.
RING_ROADS: list[tuple[str, float]] = [
    ("Ceinture Bourguiba (centre)", 1.2),
    ("Ceinture km 4", 4.0),
    ("Ceinture km 7", 7.0),
    ("Rocade km 11", 11.0),
]

# Distances (km) at which demo nodes are placed along each radial.
RADIAL_STOPS_KM = [1.2, 2.5, 4.0, 5.5, 7.0, 9.0, 11.0, 14.0]  # 14 km = exit toward other cities


@dataclass(frozen=True)
class Zone:
    name: str
    lat: float
    lon: float


ZONES: list[Zone] = [
    Zone("Sfax Médina", 34.7380, 10.7600),
    Zone("Sfax Ville (Bab Bhar)", 34.7330, 10.7660),
    Zone("Sfax Ouest", 34.7480, 10.7250),
    Zone("Sfax Sud", 34.7150, 10.7350),
    Zone("Sakiet Ezzit", 34.8000, 10.7600),
    Zone("Sakiet Eddaïer", 34.7950, 10.7950),
    Zone("Sidi Mansour", 34.7900, 10.8600),
    Zone("Chihia", 34.7900, 10.7200),
    Zone("Gremda", 34.7750, 10.6950),
    Zone("El Aïn", 34.7550, 10.6800),
    Zone("Thyna", 34.6800, 10.7000),
    Zone("Port & Zone industrielle Poudrière", 34.7250, 10.7750),
]


@dataclass(frozen=True)
class CategoryMeta:
    label_fr: str
    emoji: str
    severity: float          # intrinsic hazard 0..1
    sla_hours: int           # target time-to-resolve
    service: str             # who is responsible
    cost_tnd: tuple[int, int]  # rough repair cost range
    crew_hours: float        # typical on-site time


CATEGORIES: dict[str, CategoryMeta] = {
    "waste": CategoryMeta("Déchets", "🗑️", 0.40, 48, "Municipalité – Propreté", (50, 400), 1.0),
    "road": CategoryMeta("Routes", "🛣️", 0.70, 120, "Direction Régionale de l'Équipement", (300, 8000), 4.0),
    "lighting": CategoryMeta("Éclairage", "💡", 0.50, 72, "Municipalité / STEG", (100, 1500), 1.5),
    "traffic": CategoryMeta("Circulation", "🚦", 0.80, 24, "Police de la circulation / Municipalité", (100, 3000), 2.0),
    "school": CategoryMeta("Écoles", "🏫", 0.75, 48, "Municipalité / CRE Sfax", (100, 2000), 2.0),
    "flooding": CategoryMeta("Inondation / Assainissement", "🌊", 0.85, 24, "ONAS", (500, 15000), 5.0),
    "water": CategoryMeta("Fuite d'eau", "🚰", 0.60, 24, "SONEDE", (200, 5000), 3.0),
    "pollution": CategoryMeta("Pollution", "🏭", 0.70, 72, "ANPE", (0, 0), 2.0),
    "green": CategoryMeta("Espaces verts", "🌳", 0.25, 168, "Municipalité – Espaces verts", (50, 1000), 1.5),
    "other": CategoryMeta("Autre", "📍", 0.30, 120, "Municipalité", (0, 1000), 1.0),
}

# Tunisian emergency numbers, used by the AI assistant's safety tool.
EMERGENCY_NUMBERS = {
    "SAMU (urgence médicale)": "190",
    "Police": "197",
    "Garde nationale": "193",
    "Protection civile (pompiers)": "198",
}
