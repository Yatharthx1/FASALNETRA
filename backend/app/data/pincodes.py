"""PIN code to Village directory for Madhya Pradesh (Malwa/Nimar soybean belt).

Covers Indore, Mandsaur, Ujjain, Dewas, Dhar, Ratlam agricultural clusters.
"""

# Specific PIN code mapping
PINCODE_VILLAGE_MAP: dict[str, list[dict[str, str]]] = {
    # Indore District
    "452016": [
        {"digit": "1", "name": "कनाड़िया (Kanadia)", "slug": "kanadia"},
        {"digit": "2", "name": "बिचोली मर्दाना (Bicholi Mardana)", "slug": "bicholi_mardana"},
        {"digit": "3", "name": "तिल्लोर खुर्द (Tillor Khurd)", "slug": "tillor_khurd"},
    ],
    "452001": [
        {"digit": "1", "name": "पालदा (Palda)", "slug": "palda"},
        {"digit": "2", "name": "हुकमचंद (Hukamchand)", "slug": "hukamchand"},
        {"digit": "3", "name": "तेजाजी नगर (Tejaji Nagar)", "slug": "tejaji_nagar"},
    ],
    "452020": [
        {"digit": "1", "name": "निपानिया (Nipania)", "slug": "nipania"},
        {"digit": "2", "name": "लसूडिया (Lasudia)", "slug": "lasudia"},
        {"digit": "3", "name": "मांगलिया (Manglia)", "slug": "manglia"},
    ],
    "453111": [
        {"digit": "1", "name": "हातोद (Hatod)", "slug": "hatod"},
        {"digit": "2", "name": "बेतमा (Betma)", "slug": "betma"},
        {"digit": "3", "name": "देपालपुर (Depalpur)", "slug": "depalpur"},
    ],
    "453551": [
        {"digit": "1", "name": "सांवेर (Sanwer)", "slug": "sanwer"},
        {"digit": "2", "name": "अजनोद (Ajnod)", "slug": "ajnod"},
        {"digit": "3", "name": "डकाच्या (Dakachya)", "slug": "dakachya"},
    ],

    # Mandsaur District (Core PRD Demo Cluster)
    "458001": [
        {"digit": "1", "name": "दलोदा (Daloda)", "slug": "daloda"},
        {"digit": "2", "name": "रिठोया (Rithoya)", "slug": "rithoya"},
        {"digit": "3", "name": "बनी (Bani)", "slug": "bani"},
    ],
    "458002": [
        {"digit": "1", "name": "मुल्तानपुरा (Multanpura)", "slug": "multanpura"},
        {"digit": "2", "name": "धुंधड़का (Dhundharka)", "slug": "dhundharka"},
        {"digit": "3", "name": "निपानिया (Nipania)", "slug": "nipania"},
    ],
    "458556": [
        {"digit": "1", "name": "सीतामऊ (Sitamau)", "slug": "sitamau"},
        {"digit": "2", "name": "लदूना (Laduna)", "slug": "laduna"},
        {"digit": "3", "name": "तीतरोड़ (Titrod)", "slug": "titrod"},
    ],
    "458667": [
        {"digit": "1", "name": "पिपलिया मंडी (Piplia Mandi)", "slug": "piplia_mandi"},
        {"digit": "2", "name": "मल्हारगढ़ (Malhargarh)", "slug": "malhargarh"},
        {"digit": "3", "name": "बही पारसनाथ (Bahi Parasnath)", "slug": "bahi_parasnath"},
    ],

    # Ujjain District
    "456001": [
        {"digit": "1", "name": "तराना (Tarana)", "slug": "tarana"},
        {"digit": "2", "name": "घटिया (Ghatiya)", "slug": "ghatiya"},
        {"digit": "3", "name": "महिदपुर (Mahidpur)", "slug": "mahidpur"},
    ],

    # Dhar District
    "454001": [
        {"digit": "1", "name": "बदनावर (Badnawar)", "slug": "badnawar"},
        {"digit": "2", "name": "सरदारपुर (Sardarpur)", "slug": "sardarpur"},
        {"digit": "3", "name": "नालछा (Nalchha)", "slug": "nalchha"},
    ],
}

# Regional fallbacks based on first 3 digits of PIN code
PREFIX_DISTRICT_MAP: dict[str, list[dict[str, str]]] = {
    "452": [
        {"digit": "1", "name": "कनाड़िया (Kanadia)", "slug": "kanadia"},
        {"digit": "2", "name": "बिचोली (Bicholi)", "slug": "bicholi"},
        {"digit": "3", "name": "मांगलिया (Manglia)", "slug": "manglia"},
    ],
    "453": [
        {"digit": "1", "name": "हातोद (Hatod)", "slug": "hatod"},
        {"digit": "2", "name": "सांवेर (Sanwer)", "slug": "sanwer"},
        {"digit": "3", "name": "देपालपुर (Depalpur)", "slug": "depalpur"},
    ],
    "458": [
        {"digit": "1", "name": "दलोदा (Daloda)", "slug": "daloda"},
        {"digit": "2", "name": "सीतामऊ (Sitamau)", "slug": "sitamau"},
        {"digit": "3", "name": "पिपलिया मंडी (Piplia Mandi)", "slug": "piplia_mandi"},
    ],
    "456": [
        {"digit": "1", "name": "तराना (Tarana)", "slug": "tarana"},
        {"digit": "2", "name": "घटिया (Ghatiya)", "slug": "ghatiya"},
        {"digit": "3", "name": "महिदपुर (Mahidpur)", "slug": "mahidpur"},
    ],
    "454": [
        {"digit": "1", "name": "बदनावर (Badnawar)", "slug": "badnawar"},
        {"digit": "2", "name": "सरदारपुर (Sardarpur)", "slug": "sardarpur"},
        {"digit": "3", "name": "कुक्षी (Kukshi)", "slug": "kukshi"},
    ],
}

DEFAULT_VILLAGES: list[dict[str, str]] = [
    {"digit": "1", "name": "दलोदा (Daloda)", "slug": "daloda"},
    {"digit": "2", "name": "कनाड़िया (Kanadia)", "slug": "kanadia"},
    {"digit": "3", "name": "सीतामऊ (Sitamau)", "slug": "sitamau"},
]


def get_villages_for_pincode(pincode: str) -> list[dict[str, str]]:
    """Return village options for a given 6-digit PIN code or prefix-matched regional villages."""
    clean_pin = str(pincode).strip()
    if clean_pin in PINCODE_VILLAGE_MAP:
        return PINCODE_VILLAGE_MAP[clean_pin]

    prefix = clean_pin[:3]
    if prefix in PREFIX_DISTRICT_MAP:
        return PREFIX_DISTRICT_MAP[prefix]

    return DEFAULT_VILLAGES
