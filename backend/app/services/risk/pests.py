"""Soybean pest profiles: who the pest is, where to look it up, and what weather and habitat let it build up.

One entry per evidence cause. Used by the weather rules (rules.py), the seasonal prior from GBIF records and
Kisan Call Centre questions (seasonality.py), and the mapping of crop.health / plant.id answers onto our causes.

Weather and habitat notes follow the general soybean pest literature (ICAR-NSRI package of practices, IPM
guides); thresholds in rules.py are provisional until checked against MP field data.
"""

PESTS: dict[str, dict] = {
    "yellow_mosaic": {
        "name_en": "Yellow mosaic virus, carried by whitefly",
        "species": [("Bemisia tabaci", 2012126), ("Mungbean yellow mosaic India virus", 9886628)],
        "weather": "warm (28-33 C), dry and sunny spells with low evening humidity build whitefly; heavy rain washes it off",
        "habitat": "urad / moong next door and weedy, grassy bunds keep both the whitefly and the virus between seasons",
        # Kisan Call Centre question text (English + Hindi in Latin script) that points to this cause
        "kcc_keywords": ["yellow mosaic", "ymv", "mosaic", "white fly", "whitefly", "safed makhi", "safed makkhi",
                         "peela", "pila pad", "pili pad"],
        # crop.health names whitefly by family (Aleyrodidae)
        "kindwise_keywords": ["mosaic", "begomovirus", "bemisia", "whitefly", "yellow vein", "aleyrodidae"],
    },
    "chewing_damage": {
        "name_en": "Leaf-eating caterpillars (tobacco caterpillar, semilooper, Helicoverpa)",
        "species": [("Spodoptera litura", 5109882), ("Chrysodeixis acuta", 1785181), ("Helicoverpa armigera", 8108800)],
        "weather": "humid monsoon weeks at 24-30 C with light, broken rain; outbreaks often follow a dry break after rains",
        "habitat": "eggs under leaves; dense canopy and weedy borders shelter larvae",
        "kcc_keywords": ["caterpillar", "semilooper", "semi looper", "looper", "spodoptera", "tobacco caterpillar",
                         "leaf eating", "defoliator", "illi", "ilii", "elli", "sundi", "helicoverpa", "pod borer"],
        "kindwise_keywords": ["caterpillar", "spodoptera", "helicoverpa", "looper", "chrysodeixis", "armyworm",
                              "leaf-eating", "defoliat", "chewing",
                              # crop.health names caterpillars by family, not species
                              "noctuidae", "erebidae", "geometridae", "plusiinae"],
    },
    "girdle_beetle": {
        "name_en": "Girdle beetle",
        "species": [("Obereopsis brevis", 1158054)],
        "weather": "continuous rain and high humidity (RH over 80%) at 25-30 C in July-August; dense, late-sown crops",
        "habitat": "larvae inside the stem; crop residue and close spacing carry it over",
        "kcc_keywords": ["girdle", "girdal", "gardal", "chakra bhrung", "chakra bhrang", "stem cutting",
                         "obereopsis", "tana chhedak", "stem borer"],
        "kindwise_keywords": ["girdle", "obereopsis", "stem girdler", "cerambycid"],
    },
    "fungal": {
        "name_en": "Fungal leaf diseases (aerial blight, rust, anthracnose, leaf spots)",
        "species": [("Rhizoctonia solani", 2555201), ("Phakopsora pachyrhizi", 2514154)],
        "weather": "long leaf wetness and RH over 85% at 23-30 C (blight); cooler, very wet late-season weeks (rust)",
        "habitat": "infected residue in the soil; dense canopy that stays wet",
        "kcc_keywords": ["rust", "blight", "anthracnose", "leaf spot", "rhizoctonia", "fungus", "fungal", "phaphund",
                         "fafund", "jhulsa", "charcoal rot", "frog eye", "frogeye", "pod blight"],
        "kindwise_keywords": ["rust", "phakopsora", "blight", "rhizoctonia", "anthracnose", "colletotrichum",
                              "frogeye", "cercospora", "septoria", "leaf spot", "mildew", "fungal", "fungus",
                              "bacterial pustule", "xanthomonas", "pseudomonas"],
    },
}

# crop.health / plant.id answers that are not a pest
KINDWISE_NON_PEST = {
    "healthy": ["healthy"],
    "uniform_yellowing": ["nitrogen", "deficien", "chlorosis", "nutrient", "potassium", "sulfur", "waterlog",
                          "abiotic"],
}


def kcc_cause(text: str) -> str | None:
    """Which cause a farmer's KCC question is about (first match wins, in PESTS order)."""
    t = text.lower()
    for cause, p in PESTS.items():
        if any(k in t for k in p["kcc_keywords"]):
            return cause
    return None
