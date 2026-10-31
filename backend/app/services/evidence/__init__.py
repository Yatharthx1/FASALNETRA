"""Evidence card: every signal votes, confidence = share of all votes won by the top cause.

Weights follow the PRD (photo AI 3, traps 2, keypad 2, weather 2, crop stage 1,
advisory 1) plus the independent CLIP photo vote, the satellite patch and
neighbouring confirmed cases. A signal's own uncertainty is not given to any
cause, so a doubtful signal lowers confidence instead of inventing support.

Routing (the user flow):
    high + pest      -> voice advisory with dose from the ICAR-NSRI table; Drone Didi offered for the zone
    medium / low     -> Drone Didi (or KVK) checks the zone first, then sprays if confirmed
    non-pest cause   -> no pesticide; water / nutrient advice (low confidence -> KVK expert)
"""
from backend.app.services import advisory

PEST_CAUSES = ["yellow_mosaic", "fungal", "chewing_damage"]
CAUSES = PEST_CAUSES + ["water_stress", "nutrient"]
FIELD_SIGNALS = {"photo_ai", "photo_match", "traps", "keypad"}

WEIGHTS = {"photo_ai": 3.0, "photo_match": 1.5, "traps": 2.0, "keypad": 2.0, "weather": 2.0,
           "crop_stage": 1.0, "advisory": 1.0, "satellite": 1.0, "neighbours": 1.0}
BLURRY_FACTOR = 0.5
HIGH, MEDIUM = 0.75, 0.50
MIN_AGREEING = 3
TRAP_WHITEFLY_FULL = 10          # whiteflies per trap card at which the trap vote is full strength
LOW_SPOT_VETO = 0.6              # most of the weak patch sits in a low spot -> suspect waterlogging first

# keypad answer id -> (cause it supports when "yes")
KEYPAD_YES = {
    "whitefly_under_leaves": "yellow_mosaic",
    "yellow_mosaic_patches": "yellow_mosaic",
    "holes_in_leaves": "chewing_damage",
    "caterpillars_seen": "chewing_damage",
    "brown_spots": "fungal",
    "standing_water": "water_stress",
    "wilting_afternoon": "water_stress",
    "whole_field_pale": "nutrient",
}
PHOTO_TO_CAUSE = {"yellow_mosaic": "yellow_mosaic", "fungal": "fungal", "chewing_damage": "chewing_damage",
                  "uniform_yellowing": "nutrient"}   # even yellowing: nutrient or water, never a pest spray


def _photo(p: dict | None) -> dict[str, float]:
    if not p or p["label"] not in PHOTO_TO_CAUSE:
        return {}            # healthy / unsure: no support for any cause, but the weight still counts
    return {PHOTO_TO_CAUSE[p["label"]]: p["confidence"]}


def _keypad(answers: dict[str, bool] | None) -> dict[str, float]:
    yes = [KEYPAD_YES[k] for k, v in (answers or {}).items() if v and k in KEYPAD_YES]
    return {c: yes.count(c) / len(yes) for c in set(yes)} if yes else {}


def _weather(scores: dict[str, float] | None) -> dict[str, float]:
    if not scores:
        return {}
    total = sum(scores.values())
    return {c: s * s / total for c, s in scores.items() if total}   # strong rule keeps most of its vote


def _satellite(s: dict | None) -> dict[str, float]:
    if not s or s["pattern"] == "none":
        return {}
    if s["pattern"] == "field_wide":
        return {"nutrient": 0.6, "water_stress": 0.4}
    if s["low_spot_overlap"] >= LOW_SPOT_VETO or (s.get("water_signal") or 0) < -1.5:
        return {"water_stress": s["strength"]}
    if s["pattern"] == "patch":
        return {c: s["strength"] / len(PEST_CAUSES) for c in PEST_CAUSES}
    return {}


def _supports(p: dict[str, float]) -> str | None:
    """The single cause a signal backs; None when it splits evenly (e.g. crop stage fits every pest)."""
    if not p:
        return None
    best = max(p, key=p.get)
    return best if sum(v == p[best] for v in p.values()) == 1 else None


def build(*, photo_ai: dict | None = None, photo_match: dict | None = None, trap_counts: list[int] | None = None,
          keypad: dict[str, bool] | None = None, weather_scores: dict[str, float] | None = None, das: int | None = None,
          advisory_flags: dict[str, bool] | None = None, satellite: dict | None = None,
          neighbour_cases: list[str] | None = None, zone_acres: float | None = None) -> dict:
    signals: dict[str, tuple[float, dict[str, float]]] = {}

    if photo_ai is not None:
        w = WEIGHTS["photo_ai"] * (BLURRY_FACTOR if not photo_ai.get("quality", {}).get("ok", True) else 1.0)
        signals["photo_ai"] = (w, _photo(photo_ai))
    if photo_match is not None:
        signals["photo_match"] = (WEIGHTS["photo_match"], _photo(photo_match))
    if trap_counts:
        signals["traps"] = (WEIGHTS["traps"], {"yellow_mosaic": min(1.0, max(trap_counts) / TRAP_WHITEFLY_FULL)})
    if keypad:
        signals["keypad"] = (WEIGHTS["keypad"], _keypad(keypad))
    if weather_scores:
        signals["weather"] = (WEIGHTS["weather"], _weather(weather_scores))
    if das is not None:
        vulnerable = [c for c in PEST_CAUSES if advisory.find(c)["vulnerable_das"][0] <= das <= advisory.find(c)["vulnerable_das"][1]]
        signals["crop_stage"] = (WEIGHTS["crop_stage"], {c: 1 / len(vulnerable) for c in vulnerable} if vulnerable else {})
    if advisory_flags:
        flagged = [c for c, v in advisory_flags.items() if v]
        signals["advisory"] = (WEIGHTS["advisory"], {c: 1 / len(flagged) for c in flagged} if flagged else {})
    if satellite is not None:
        signals["satellite"] = (WEIGHTS["satellite"], _satellite(satellite))
    if neighbour_cases:
        signals["neighbours"] = (WEIGHTS["neighbours"],
                                 {c: neighbour_cases.count(c) / len(neighbour_cases) for c in set(neighbour_cases)})

    total_w = sum(w for w, _ in signals.values()) or 1.0
    votes = {c: sum(w * p.get(c, 0.0) for w, p in signals.values()) for c in CAUSES}
    top = max(votes, key=votes.get)
    confidence = votes[top] / total_w
    agreeing = [name for name, (_, p) in signals.items() if _supports(p) == top]
    has_field = any(n in FIELD_SIGNALS for n in agreeing)

    if confidence >= HIGH and has_field and len(agreeing) >= MIN_AGREEING:
        level = "high"
    elif confidence >= MEDIUM:
        level = "medium"
    else:
        level = "low"

    low_spot = bool(satellite and satellite.get("low_spot_overlap", 0) >= LOW_SPOT_VETO)
    if top not in PEST_CAUSES:
        action = "advise_no_pesticide" if level != "low" else "expert_check"   # KVK, not a drone
    elif level == "high" and not low_spot:
        action = "advise_spray"           # farmer gets dose by voice; key 1 books Drone Didi for the zone only
    else:
        action = "didi_verify"            # Drone Didi / KVK checks the zone before anything is sprayed

    plan = advisory.spray_plan(top, zone_acres) if zone_acres else None
    return {
        "cause": top,
        "name_hi": advisory.find(top)["name_hi"],
        "confidence": round(confidence, 3),
        "level": level,
        "action": action,
        "spray_allowed": action == "advise_spray",
        "agreeing_signals": agreeing,
        "low_spot_warning": low_spot,
        "wording": "shak" if level != "high" else "zyada sambhavna",   # never a certain diagnosis
        "signals": [
            {"name": n, "weight": round(w, 2), "supports": _supports(p),
             "strength": round(max(p.values()), 2) if p else 0.0, "share": round(w * p.get(top, 0.0) / total_w, 3)}
            for n, (w, p) in signals.items()
        ],
        "alternatives": sorted(({"cause": c, "share": round(v / total_w, 3)} for c, v in votes.items() if c != top and v),
                               key=lambda x: -x["share"])[:2],
        "plan": plan,
    }
