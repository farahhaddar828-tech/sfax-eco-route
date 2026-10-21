"""'Eco-Route Assistant' — a tool-using agent that helps a citizen react to a
problem in the street: is it dangerous, who to call, how to get around it,
and turning a messy description into a well-formed report.

Grounding: the model never invents facts about the city. It calls tools that
query the live report database and the road graph; the safety protocols and
emergency numbers are fixed data, not generated.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from ..data.sfax import CATEGORIES, EMERGENCY_NUMBERS
from ..graph.road_graph import get_graph, haversine_m
from ..models import Report, Status
from .llm import LLM, AgentResult, Tool

SAFETY_PROTOCOLS = {
    "fallen_wire": [
        "Restez à au moins 10 m du câble et éloignez les autres personnes.",
        "Ne touchez ni le câble ni ce qui est en contact avec (eau, voiture, clôture).",
        "Appelez la Protection civile (198) et signalez à la STEG.",
    ],
    "flooding": [
        "Ne traversez pas une rue inondée, ni à pied ni en voiture : 30 cm d'eau courante peuvent emporter une voiture.",
        "Méfiez-vous des bouches d'égout ouvertes invisibles sous l'eau.",
        "Montez en hauteur si l'eau monte ; appelez le 198 si quelqu'un est en danger.",
    ],
    "fire": [
        "Éloignez-vous et appelez immédiatement la Protection civile (198).",
        "Si la fumée est épaisse, restez bas et couvrez nez et bouche.",
        "N'utilisez pas d'eau sur un feu électrique ou d'huile.",
    ],
    "accident": [
        "Sécurisez la zone (feux de détresse, triangle) sans vous mettre en danger.",
        "Appelez le SAMU (190) s'il y a des blessés, la Police (197) ou la Garde nationale (193) hors ville.",
        "Ne déplacez pas un blessé sauf danger immédiat (feu, circulation).",
    ],
    "gas_leak": [
        "N'actionnez aucun interrupteur, ne faites pas de flamme, ne téléphonez pas sur place.",
        "Éloignez-vous, puis appelez la Protection civile (198) et la STEG.",
    ],
    "traffic_light_out": [
        "Traitez le carrefour comme une priorité à droite et ralentissez fortement.",
        "Signalez-le : c'est une urgence de circulation (priorité élevée).",
    ],
    "pothole": [
        "Contournez seulement si c'est sans risque ; ralentissez, surtout à deux-roues.",
        "Signalez-le avec une photo : la priorité dépend de l'importance de la route.",
    ],
}

KEYWORDS = {
    "waste": ["déchet", "dechet", "poubelle", "ordure", "zbel", "décharge", "sac"],
    "road": ["trou", "nid", "chaussée", "chaussee", "route abîmée", "goudron", "asphalte", "fissure"],
    "lighting": ["câble électrique", "cable electrique", "fil électrique", "poteau", "lampadaire", "éclairage", "eclairage", "lumière", "noir", "ampoule"],
    "traffic": ["feu", "embouteillage", "bouchon", "accident", "circulation", "signalisation", "stop"],
    "school": ["école", "ecole", "élève", "eleve", "lycée", "collège", "enfants"],
    "flooding": ["inond", "eau stagnante", "égout", "egout", "assainissement", "pluie", "onas"],
    "water": ["fuite", "sonede", "canalisation", "tuyau"],
    "pollution": ["fumée", "fumee", "odeur", "pollution", "sous-produit", "phosphogypse", "usine", "sitex", "nox"],
    "green": ["arbre", "jardin", "parc", "espace vert", "palmier"],
}
DANGER_WORDS = ["câble", "cable", "fil électrique", "incendie", "feu ", "gaz", "blessé", "blesse",
                "accident", "inond", "effondr", "enfant"]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s.lower())


def rule_triage(text: str) -> dict:
    t = _norm(text)
    # longer phrases are more specific ("câble électrique" beats "chaussée"), so weight by length
    scores = {c: sum(t.count(k) * len(k) for k in kws) for c, kws in KEYWORDS.items()}
    cat = max(scores, key=scores.get)
    cat = cat if scores[cat] > 0 else "other"
    danger = any(w in t for w in DANGER_WORDS)
    return {
        "category": cat,
        "suggested_urgency": 80 if danger else int(CATEGORIES[cat].severity * 70),
        "summary": re.sub(r"\s+", " ", text.strip())[:160],
        "danger_to_people": danger,
        "engine": "rules",
    }


async def triage(text: str, llm: LLM | None = None, lang: str | None = None) -> dict:
    """Classify a free-text description. LLM if available, rules otherwise (and on any failure).

    ``lang`` is the language the app is being read in. The summary is shown
    straight back to the citizen, so it has to be in that language rather than
    in whichever language the prompt happens to be written in. The rule-based
    fallback echoes the citizen's own words, so it needs no translation.
    """
    llm = llm or LLM()
    if not llm.enabled or len(text.strip()) < 8:
        return rule_triage(text)
    cats = ", ".join(f"{k} ({v.label_fr})" for k, v in CATEGORIES.items())
    summary_lang = LANGUAGE_NAMES.get((lang or "").strip().lower(), "francais")
    try:
        out = await llm.complete_json(
            "Tu tries des signalements urbains à Sfax (Tunisie). Le texte peut être en français, "
            "en arabe tunisien (darija, y compris en lettres latines) ou en anglais.",
            f"Catégories possibles: {cats}.\nTexte: «{text}»\n"
            'Réponds: {"category": "<clé>", "suggested_urgency": 0-100, '
            f'"summary": "<résumé factuel en {summary_lang}, 1 phrase>", '
            '"danger_to_people": true|false}',
        )
        if out.get("category") not in CATEGORIES:
            out["category"] = "other"
        out["suggested_urgency"] = max(0, min(100, int(out.get("suggested_urgency", 50))))
        out["engine"] = llm.provider

        # A small model answers "danger" to almost anything, which pins every report
        # to the critical floor. Require the deterministic keyword check to agree.
        out["danger_to_people"] = bool(out.get("danger_to_people")) and any(
            w in _norm(text) for w in DANGER_WORDS
        )
        return out
    except Exception:  # noqa: BLE001
        return rule_triage(text)


SYSTEM_PROMPT = """Tu es l'assistant de Sfax Eco-Route. Tu aides un citoyen de Sfax à réagir à un problème urbain.
Priorités, dans cet ordre :
1. Sécurité des personnes. S'il y a un danger immédiat, commence par l'action de sécurité et le numéro d'urgence (outil get_safety_protocol / emergency_numbers). Ne remplace jamais les secours.
2. Contexte réel : utilise les outils (signalements à proximité, impact d'une fermeture de route, itinéraire alternatif) plutôt que de supposer. N'invente aucun chiffre ni nom de rue.
3. Action : propose de créer un signalement bien formé (draft_report) — le citoyen le valide dans l'app.
Réponds dans la langue de l'utilisateur (français, darija ou anglais), de façon brève et concrète, avec des étapes numérotées si utile."""

# The numbers go in the prompt itself, not just the tool: a small local model
# otherwise falls back on French emergency numbers (15/17/18) from its training data.
SYSTEM_PROMPT += (
    "\n\nNUMEROS D'URGENCE EN TUNISIE, les seuls valides: "
    + " - ".join(f"{k}: {v}" for k, v in EMERGENCY_NUMBERS.items())
    + ". N'invente JAMAIS un autre numero d'urgence."
    + " Les numeros francais (15, 17, 18, 112) sont FAUX en Tunisie: ne les cite jamais."
    + " En cas de doute, appelle l'outil emergency_numbers."
)


def build_tools(db: Session, user_pos: tuple[float, float] | None) -> list[Tool]:
    graph = get_graph()

    def emergency_numbers() -> dict:
        return EMERGENCY_NUMBERS

    def get_safety_protocol(situation: str) -> dict:
        return {"situation": situation, "steps": SAFETY_PROTOCOLS.get(situation, SAFETY_PROTOCOLS["accident"]),
                "emergency_numbers": EMERGENCY_NUMBERS}

    def nearby_reports(lat: float | None = None, lon: float | None = None, radius_m: int = 500) -> list[dict]:
        lat, lon = (lat, lon) if lat is not None else (user_pos or (None, None))
        if lat is None:
            return [{"error": "position inconnue"}]
        open_r = db.query(Report).filter(Report.status.notin_([Status.resolved, Status.rejected])).all()
        rows = [(haversine_m(lat, lon, r.lat, r.lon), r) for r in open_r]
        return [{"distance_m": round(d), "category": r.category.value, "road": r.road_name,
                 "priority": r.priority_label, "description": r.description[:120], "upvotes": r.upvotes}
                for d, r in sorted(rows, key=lambda x: x[0]) if d <= radius_m][:10]

    def road_closure_impact(lat: float, lon: float) -> dict:
        u, v = graph.nearest_edge(lat, lon)
        return graph.closure_impact(u, v, samples=40)

    def safe_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> dict:
        from ..api.routing import hazards_from_db
        res = graph.route((origin_lat, origin_lon), (dest_lat, dest_lon), hazards_from_db(db))
        for k in ("fastest", "eco_route"):
            res[k].pop("coords", None)
            res[k].pop("nodes", None)
        return res

    def draft_report(category: str, description: str, urgency: int,
                     lat: float | None = None, lon: float | None = None) -> dict:
        pos = (lat, lon) if lat is not None else user_pos
        return {"draft": {"category": category if category in CATEGORIES else "other",
                          "description": description, "citizen_urgency": max(0, min(100, urgency)),
                          "lat": pos[0] if pos else None, "lon": pos[1] if pos else None},
                "note": "Brouillon : l'utilisateur doit confirmer dans l'application."}

    num = {"type": "number"}
    return [
        Tool("emergency_numbers", "Numéros d'urgence tunisiens.", {"type": "object", "properties": {}}, emergency_numbers),
        Tool("get_safety_protocol", "Consignes de sécurité vérifiées pour une situation.",
             {"type": "object", "properties": {"situation": {"type": "string", "enum": list(SAFETY_PROTOCOLS)}},
              "required": ["situation"]}, get_safety_protocol),
        Tool("nearby_reports", "Signalements ouverts autour d'un point (par défaut la position de l'utilisateur).",
             {"type": "object", "properties": {"lat": num, "lon": num, "radius_m": {"type": "integer"}}}, nearby_reports),
        Tool("road_closure_impact", "Impact sur le réseau si la route la plus proche du point est bloquée (détour, trajets touchés).",
             {"type": "object", "properties": {"lat": num, "lon": num}, "required": ["lat", "lon"]}, road_closure_impact),
        Tool("safe_route", "Itinéraire le plus rapide vs itinéraire évitant les problèmes signalés.",
             {"type": "object", "properties": {"origin_lat": num, "origin_lon": num, "dest_lat": num, "dest_lon": num},
              "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon"]}, safe_route),
        Tool("draft_report", "Prépare un signalement structuré à faire valider par le citoyen.",
             {"type": "object", "properties": {"category": {"type": "string", "enum": list(CATEGORIES)},
                                               "description": {"type": "string"}, "urgency": {"type": "integer"},
                                               "lat": num, "lon": num},
              "required": ["category", "description", "urgency"]}, draft_report),
    ]


LANGUAGE_NAMES = {"fr": "francais", "en": "anglais", "ar": "arabe"}


def language_clause(lang: str | None) -> str:
    """Pin the reply language when the user picked one in the app's settings.

    Without this the prompt only says 'answer in the user's language', which a
    small model reads off the question rather than off the chosen setting.
    """
    name = LANGUAGE_NAMES.get((lang or "").strip().lower())
    if not name:
        return ""
    return (f"\nL'utilisateur a choisi la langue: {name}. Reponds UNIQUEMENT en {name}, "
            "quelle que soit la langue de sa question.")


async def ask(db: Session, history: list[dict], user_pos: tuple[float, float] | None,
              lang: str | None = None) -> AgentResult:
    llm = LLM()
    tools = build_tools(db, user_pos)
    if llm.enabled:
        try:
            ctx = f"\nPosition de l'utilisateur : {user_pos}." if user_pos else ""
            return await llm.run_agent(SYSTEM_PROMPT + ctx + language_clause(lang), history, tools)
        except Exception as e:  # noqa: BLE001
            fallback = await _rule_assistant(history, tools)
            fallback.text = f"(IA indisponible : {type(e).__name__}) " + fallback.text
            return fallback
    return await _rule_assistant(history, tools)


async def _rule_assistant(history: list[dict], tools: list[Tool]) -> AgentResult:
    """Deterministic assistant used without an LLM: triage + safety + draft."""
    last = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    tri = rule_triage(last)
    t = _norm(last)
    situation = ("fallen_wire" if "câble" in t or "cable" in t or "fil" in t else
                 "flooding" if "inond" in t else "fire" if "incendie" in t or "fumée" in t else
                 "gas_leak" if "gaz" in t else "accident" if "accident" in t or "blessé" in t else
                 "traffic_light_out" if "feu" in t and tri["category"] == "traffic" else
                 "pothole" if tri["category"] == "road" else None)
    lines = []
    if situation:
        lines.append("Consignes de sécurité :")
        lines += [f"{i}. {s}" for i, s in enumerate(SAFETY_PROTOCOLS[situation], 1)]
    meta = CATEGORIES[tri["category"]]
    lines.append(f"\nJe propose un signalement « {meta.emoji} {meta.label_fr} » (urgence {tri['suggested_urgency']}/100), "
                 f"transmis à : {meta.service}. Confirmez-le dans l'écran de signalement.")
    return AgentResult("\n".join(lines), [{"tool": "rules", "args": tri}], "none", "rules")
