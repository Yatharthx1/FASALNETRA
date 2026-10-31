"""Farmer advisory text for a high-confidence case: an LLM writes it from the crop knowledge pack, a checker
guards it, a fixed template is the fallback.

Rules the output must keep (CLAUDE.md):
- doses come only from the ICAR-NSRI table: the LLM writes placeholders ({PRODUCT}, {QUANTITY} ...) that are filled
  here from the facts, and any other number it writes must already be in the facts, else the text is rejected;
- never a certain diagnosis: the Hindi must say "शक" (suspected).

Cost (cost-aware-llm-pipeline): fast model only (a short rewrite, no escalation), same tracker and budget as the
vision calls, fixed prompt prefix (instructions + crop examples) before the case facts so it can be cached.

    ADVISORY_PROVIDER   gemini (default when a key is set) | template
"""
import json
import logging
import os

from backend.app.services.advisory import knowledge

log = logging.getLogger(__name__)

PLACEHOLDERS = ("PRODUCT", "QUANTITY", "UNIT", "WATER_L", "ZONE_ACRES", "WINDOW", "REPEAT_DAYS")

INSTRUCTIONS = """You write a short spoken advisory in simple Hindi for a soybean or other crop farmer in Madhya Pradesh
who may not read. You are given FACTS about one field. Use only these facts; add nothing from your own knowledge.

Rules:
1. Never write a pesticide name, dose, quantity, water amount or spray time yourself. Write the placeholders
   {PRODUCT} {QUANTITY} {UNIT} {WATER_L} {ZONE_ACRES} {WINDOW} {REPEAT_DAYS}; they are filled in later.
2. Any other number you write must appear in FACTS. If unsure, leave the number out.
3. It is a suspicion, never certain: always use the word "शक".
4. Spray only the affected patch, never the whole field. If FACTS.spray is null, say no pesticide is needed.
5. Order: what is suspected and where; first the cultural step from FACTS (stage_practice_hi / icar_practices);
   then the spray with placeholders and the spray window; one line on what to watch next.
6. say_hi: at most 2 short sentences for a phone call. advisory_hi: at most 6 sentences. advisory_en: the same in
   plain English.
"""

SCHEMA = {
    "type": "object",
    "properties": {"say_hi": {"type": "string"}, "advisory_hi": {"type": "string"}, "advisory_en": {"type": "string"}},
    "required": ["say_hi", "advisory_hi", "advisory_en"],
    "propertyOrdering": ["say_hi", "advisory_hi", "advisory_en"],
}


class Rejected(ValueError):
    """The generated text broke a rule; the template is used instead."""


def _fill(text: str, facts: dict) -> str:
    spray = facts.get("spray") or {}
    values = {"PRODUCT": spray.get("product", ""), "QUANTITY": f"{spray['quantity']:g}" if spray else "",
              "UNIT": spray.get("unit", ""), "WATER_L": f"{spray['water_l']:g}" if spray else "",
              "ZONE_ACRES": f"{facts['zone_acres']:g}" if facts.get("zone_acres") else "",
              "WINDOW": facts.get("spray_window") or "सुबह", "REPEAT_DAYS": str(spray.get("repeat_after_days") or "")}
    for k in PLACEHOLDERS:
        text = text.replace("{" + k + "}", values[k])
    return " ".join(text.split())


def check(out: dict, facts: dict) -> dict:
    """Fill placeholders and enforce the rules; raises Rejected."""
    filled = {k: _fill(out.get(k, ""), facts) for k in ("say_hi", "advisory_hi", "advisory_en")}
    if not filled["say_hi"] or not filled["advisory_hi"]:
        raise Rejected("empty text")
    if "{" in "".join(filled.values()):
        raise Rejected("unknown placeholder")
    stray = knowledge.numbers_in(filled) - set(facts["allowed_numbers"])
    if stray:
        raise Rejected(f"numbers not in the facts: {sorted(stray)}")
    if "शक" not in filled["advisory_hi"]:
        raise Rejected("Hindi advisory does not say 'शक' (suspected)")
    if not facts.get("spray") and "{PRODUCT}" in out.get("advisory_hi", ""):
        raise Rejected("spray mentioned where the table has no chemical")
    return filled


def template(facts: dict) -> dict:
    """Deterministic advisory from the same facts; always available (no key, offline, or a rejected LLM answer)."""
    zone = f"लगभग {facts['zone_acres']:g} एकड़ हिस्से में " if facts.get("zone_acres") else ""
    head = (f"आपकी {facts['crop_hi']} {facts['stage_hi']} अवस्था में है ({facts['days_after_sowing']} दिन)। "
            f"{zone}{facts['cause_hi']} का शक है ({facts['confidence_pct']} प्रतिशत, "
            f"{', '.join(facts['agreeing_hi'][:3]) or 'खेत की जांच'} के आधार पर)।")
    practice = facts.get("stage_practice_hi") or ""
    spray = facts.get("spray")
    if spray:
        window = f" सुबह {facts['spray_window']} बजे के आसपास, जब हवा धीमी हो और बारिश न हो" if facts.get("spray_window") else ""
        act = (f"फिर सिर्फ उसी हिस्से में {spray['product']} {spray['quantity']:g} {spray['unit']} को "
               f"{spray['water_l']:g} लीटर पानी में मिलाकर छिड़काव कीजिए{window}। पूरे खेत में छिड़काव मत कीजिए।")
        say = f"आपकी {facts['crop_hi']} में {facts['cause_hi']} का शक है। सिर्फ बीमार हिस्से में {spray['product']} का छिड़काव कीजिए, पूरे खेत में नहीं।"
        en_act = (f"Then spray only that patch with {spray['product']}, {spray['quantity']:g} {spray['unit']} in "
                  f"{spray['water_l']:g} L of water" + (f", around {facts['spray_window']} when it is calm and dry" if facts.get("spray_window") else "")
                  + ". Do not spray the whole field.")
    else:
        act = "इसमें कीटनाशक की ज़रूरत नहीं है।"
        say = f"आपकी {facts['crop_hi']} में {facts['cause_hi']} का शक है। इसमें कीटनाशक की ज़रूरत नहीं है।"
        en_act = "No pesticide is needed for this."
    en = (f"Your {facts['crop']} is {facts['days_after_sowing']} days old. Suspected {facts['cause'].replace('_', ' ')}"
          + (f" on about {facts['zone_acres']:g} acres" if facts.get("zone_acres") else "")
          + f" ({facts['confidence_pct']}% confidence). "
          + "".join(f"{p.rstrip('.')}. " for p in facts.get("icar_practices", [])[:2]) + en_act)
    return {"say_hi": say, "advisory_hi": " ".join(f"{head} {practice} {act}".split()), "advisory_en": " ".join(en.split()),
            "source": "template"}


def _ask_gemini(facts: dict) -> dict:
    from google.genai import types

    from backend.app.services.vision import llm

    examples = knowledge.EXAMPLES.get(facts["crop"].lower(), [])
    prefix = INSTRUCTIONS + "\nEXAMPLES (tone and order only; their facts are not this field's):\n" + \
        "\n".join(json.dumps(e, ensure_ascii=False) for e in examples)
    case = {k: v for k, v in facts.items() if k != "allowed_numbers"}
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prefix),
                                                 types.Part.from_text(text="FACTS:\n" + json.dumps(case, ensure_ascii=False))])]
    config = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json", response_schema=SCHEMA)
    text, rec = llm._call(llm.FAST_MODEL, contents, config)
    llm.tracker = llm.tracker.add(rec)
    return {**json.loads(text), "model": llm.FAST_MODEL}


def provider() -> str:
    p = os.environ.get("ADVISORY_PROVIDER", "").strip().lower()
    if p:
        return p
    return "gemini" if (os.environ.get("VISION_API_KEY") or os.environ.get("GEMINI_API_KEY")) else "template"


def write(facts: dict, ask=None) -> dict:
    """Advisory for one high-confidence case. `ask` (facts -> raw LLM dict) is injectable for tests."""
    use_llm = ask is not None or provider() == "gemini"
    if not use_llm:
        return template(facts)
    from backend.app.services.vision import llm
    if ask is None and llm.tracker.over_budget:
        return {**template(facts), "note": "LLM budget spent"}
    try:
        raw = (ask or _ask_gemini)(facts)
        return {**check(raw, facts), "source": "llm", "model": raw.get("model")}
    except Rejected as exc:
        log.warning("Advisory LLM answer rejected: %s", exc)
        return {**template(facts), "note": f"LLM answer rejected: {exc}"}
    except Exception as exc:  # noqa: BLE001 -- network, quota, bad JSON: the farmer still gets an advisory
        log.warning("Advisory LLM failed: %s", exc)
        return {**template(facts), "note": "LLM unavailable"}
