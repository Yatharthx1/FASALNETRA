"""Soybean (Glycine max) Specialist Agro-Intelligence Engine.

Tailored for Madhya Pradesh (Malwa and Nimar plateau, Mandsaur, Ujjain, Indore),
following research and package of practices from ICAR-IISR (Indian Institute of
Soybean Research, Indore) and JNKVV Jabalpur.

Provides:
  1. Phenological Growth Stage Modeling (Fehr-Caviness & BBCH scale from DAS)
  2. Stage-specific Economic Threshold Levels (ETL) and scouting guidance
  3. Girdle Beetle (Obereopsis brevis) and Stem Borer risk scoring
  4. Foliar nutrition roadmap (flower retention, pod filling, oil synthesis)
  5. Varietal traits reference (JS 335, JS 95-60, JS 20-34, NRC 37, RVS 2001-4)
"""
from typing import Any

# Fehr-Caviness & BBCH Phenological Growth Stages for Soybean in MP
SOYBEAN_STAGES = [
    {
        "stage_code": "VE",
        "stage_name_en": "Emergence (VE)",
        "stage_name_hi": "अंकुरण एवं जमाव (VE)",
        "das_min": 0,
        "das_max": 7,
        "description_en": "Cotyledons have emerged above soil surface. Seedling establishing root system.",
        "description_hi": "बीज अंकुरित होकर जमीन से बाहर आ चुके हैं। जड़ प्रणाली स्थापित हो रही है।",
        "water_sensitivity": "moderate",
        "key_threats": ["seed_rot", "collar_rot", "damping_off"],
        "etl": "Any seedling mortality > 10%",
        "cultural_guidance_hi": "खेत में जलभराव न होने दें। जल निकासी नालियां खुली रखें।",
        "cultural_guidance_en": "Prevent water accumulation; ensure drainage channels are clear.",
        "foliar_nutrition": None,
    },
    {
        "stage_code": "VC_V1",
        "stage_name_en": "Unifoliate to 1st Trifoliate (VC-V1)",
        "stage_name_hi": "प्राथमिक पत्ती से पहली तिपत्तिया (VC-V1)",
        "das_min": 8,
        "das_max": 20,
        "description_en": "First unifoliate and trifoliate leaves unfolded. Node development begins.",
        "description_hi": "पहली तिपत्तिया पत्तियां खुल चुकी हैं। तने की गांठों का विकास शुरू।",
        "water_sensitivity": "low",
        "key_threats": ["stem_fly", "early_whitefly", "collar_rot"],
        "etl": "Stem fly: > 10% infested seedlings with exit holes or tunnelled stems.",
        "cultural_guidance_hi": "शुरुआती खरपतवार नियंत्रण (डोरा/कुल्पा) करें। पीली मक्खी के लिए पीले चिपचिपे ट्रैप लगाएं।",
        "cultural_guidance_en": "First interculture/weeding; install early yellow sticky traps (15-20/acre).",
        "foliar_nutrition": {
            "product": "Water-soluble 19:19:19 NPK",
            "dose": "1.0 kg/acre (100 L water)",
            "purpose_hi": "जड़ों की मजबूती और शुरुआती वानस्पतिक वृद्धि",
            "purpose_en": "Vigorous root establishment and early vegetative vigor",
        },
    },
    {
        "stage_code": "V2_V3",
        "stage_name_en": "Branching & Mid-Vegetative (V2-V3)",
        "stage_name_hi": "शाखाएं एवं वानस्पतिक वृद्धि (V2-V3)",
        "das_min": 21,
        "das_max": 35,
        "description_en": "Rapid branching and canopy expansion. Nodulation actively fixing nitrogen.",
        "description_hi": "तेजी से शाखाओं का फैलाव और पत्तियों की वृद्धि। जड़ों में गांठे सक्रिय रूप से नाइट्रोजन स्थिरीकरण कर रही हैं।",
        "water_sensitivity": "moderate",
        "key_threats": ["girdle_beetle", "yellow_mosaic", "semilooper"],
        "etl": "Girdle beetle: 5% ring-cut petioles; Whitefly: 5 adults/leaf; Semilooper: 3 larvae/meter row.",
        "cultural_guidance_hi": "चक्र भृंग (गर्डल बीटल) से कटे डंठल तोड़कर नष्ट करें। टी-आकार की पक्षी खूंटियां (40 प्रति एकड़) लगाएं।",
        "cultural_guidance_en": "Remove ring-cut petioles immediately; install 40 T-shaped bird perches per acre.",
        "foliar_nutrition": {
            "product": "Water-soluble 19:19:19 NPK + Chelated Micronutrients",
            "dose": "1.0 kg/acre",
            "purpose_hi": "शाखाओं की संख्या बढ़ाना और क्लोरोफिल सुरक्षा",
            "purpose_en": "Branch multiplication and chlorophyll enhancement",
        },
    },
    {
        "stage_code": "R1_R2",
        "stage_name_en": "Beginning Bloom to Full Bloom (R1-R2)",
        "stage_name_hi": "फूल आने की शुरुआत से पूर्ण फूल (R1-R2)",
        "das_min": 36,
        "das_max": 50,
        "description_en": "Open flowers present on nodes. CRITICAL phenological stage: moisture stress or pest damage causes irreparable yield loss.",
        "description_hi": "गांठों पर फूल खिल रहे हैं। यह फसल की सर्वाधिक संवेदनशील अवस्था है: इस समय सूखा या कीट से भारी पैदावार का नुकसान होता है।",
        "water_sensitivity": "critical",
        "key_threats": ["yellow_mosaic", "girdle_beetle", "aerial_blight", "spodoptera"],
        "etl": "Whitefly: 5-8/leaf (YMV vector); Semilooper: 3 larvae/meter; Aerial blight: Initial water-soaked canopy patches.",
        "cultural_guidance_hi": "इस समय रासायनिक कीटनाशक का अंधाधुंध छिड़काव न करें जिससे परागण करने वाले मित्र कीट न मरें। केवल लक्षित पैच पर स्प्रे करें।",
        "cultural_guidance_en": "Avoid broadcast harsh chemicals to protect pollinating insects. Restrict spraying to satellite-flagged patches only.",
        "foliar_nutrition": {
            "product": "Water-soluble 0:52:34 (Monopotassium Phosphate) + Boron 20%",
            "dose": "1.0 kg 0:52:34 + 100 g Boron per acre",
            "purpose_hi": "फूलों को झड़ने से रोकना, परागण में सुधार और अधिक फली सेटिंग",
            "purpose_en": "Prevent flower abortion, enhance pollination, and maximize pod setting",
        },
    },
    {
        "stage_code": "R3_R4",
        "stage_name_en": "Beginning Pod to Full Pod (R3-R4)",
        "stage_name_hi": "फली बनना एवं पूर्ण फली (R3-R4)",
        "das_min": 51,
        "das_max": 68,
        "description_en": "Pods developing up to full length (2-3 cm). High nutrient and water demand.",
        "description_hi": "फलियों का विकास और लंबाई पूर्ण होना। पौधे को भरपूर नमी और पोटाश की आवश्यकता।",
        "water_sensitivity": "critical",
        "key_threats": ["pod_borer", "anthracnose", "aerial_blight", "charcoal_rot"],
        "etl": "Pod borer (Helicoverpa): 1 larva/meter row or fresh pod holes > 5%.",
        "cultural_guidance_hi": "फलियों में छेद करने वाली इल्ली की निगरानी करें। खेत में नमी संरक्षित रखें।",
        "cultural_guidance_en": "Monitor pod borers; maintain soil moisture to avoid early pod drop.",
        "foliar_nutrition": {
            "product": "Water-soluble 13:0:45 (Potassium Nitrate) or 0:0:50 (SOP)",
            "dose": "1.0 kg/acre in 120 L water",
            "purpose_hi": "फलियों में दानों की संख्या और फली का वजन बढ़ाना",
            "purpose_en": "Increases seed count per pod and grain density",
        },
    },
    {
        "stage_code": "R5_R6",
        "stage_name_en": "Beginning Seed to Full Seed (R5-R6)",
        "stage_name_hi": "दाना भराव अवस्था (R5-R6)",
        "das_min": 69,
        "das_max": 85,
        "description_en": "Rapid accumulation of dry matter, protein, and oil into the seeds. Lower leaves begin yellowing naturally.",
        "description_hi": "दानों में तेजी से तेल और प्रोटीन का भराव। निचली पत्तियां स्वाभाविक रूप से पीली पड़ना शुरू होती हैं।",
        "water_sensitivity": "high",
        "key_threats": ["rust", "pod_blight", "charcoal_rot", "stink_bug"],
        "etl": "Rust pustules visible on 10% lower leaves during continuous drizzle.",
        "cultural_guidance_hi": "प्राकृतिक पीलापन और बीमारी के फर्क को समझें। इस अवस्था के बाद कीटनाशक छिड़काव बंद करें।",
        "cultural_guidance_en": "Distinguish natural senescence from disease; cease chemical sprays 15 days before harvest.",
        "foliar_nutrition": {
            "product": "0:0:50 Potassium Sulphate",
            "dose": "1.0 kg/acre",
            "purpose_hi": "दाने चमकदार, भारी और तेल प्रतिशत में वृद्धि",
            "purpose_en": "Plump, lustrous seeds and elevated oil content percentage",
        },
    },
    {
        "stage_code": "R7_R8",
        "stage_name_en": "Maturity to Harvest (R7-R8)",
        "stage_name_hi": "पूर्ण परिपक्वता एवं कटाई (R7-R8)",
        "das_min": 86,
        "das_max": 115,
        "description_en": "95% pods turned mature brown/khaki color. Moisture content dropping to 14-15%. Ready for threshing.",
        "description_hi": "95% फलियां भूरे/खाकी रंग में बदल चुकी हैं। दाने में नमी 14-15% तक। कटाई और गहाई के लिए तैयार।",
        "water_sensitivity": "none",
        "key_threats": ["pod_shattering", "post_rain_grain_damage"],
        "etl": "Harvest immediately when pod rattle sound is heard on shaking.",
        "cultural_guidance_hi": "फलियों के चटकने (शटरिंग) से पहले सुबह या शाम के समय कटाई करें जब नमी रहे।",
        "cultural_guidance_en": "Harvest during morning/evening hours to prevent shattering losses.",
        "foliar_nutrition": None,
    },
]

# Popular Soybean Varieties in Madhya Pradesh (Malwa & Nimar)
MP_SOYBEAN_VARIETIES = {
    "JS 335": {
        "institution": "JNKVV Jabalpur",
        "duration_days": "95-100",
        "suitability": "State-wide Malwa/Nimar/Bundelkhand",
        "traits_hi": "सर्वाधिक लोकप्रिय, फली चटकने के प्रति प्रतिरोधी, उच्च उपज क्षमता, पीले मोज़ेक के प्रति संवेदनशील।",
        "traits_en": "Most widely sown in MP; shatter resistant; high yield potential; susceptible to YMV.",
    },
    "JS 95-60": {
        "institution": "JNKVV Jabalpur",
        "duration_days": "82-85",
        "suitability": "Early harvest, rainfed regions, potato/wheat double crop",
        "traits_hi": "अति शीघ्र पकने वाली (82-85 दिन), सूखा टालने में सक्षम, आलू-गेहूं फसल चक्र के लिए उत्तम।",
        "traits_en": "Ultra early (82-85 days); escapes terminal drought; ideal for potato-wheat rotation.",
    },
    "JS 20-34": {
        "institution": "JNKVV Jabalpur",
        "duration_days": "85-88",
        "suitability": "Malwa Plateau",
        "traits_hi": "शीघ्र पकने वाली, चक्र भृंग और तना मक्खी के प्रति मध्यम प्रतिरोधी, जलभराव सहने योग्य।",
        "traits_en": "Early maturing; moderately resistant to girdle beetle and stem fly; tolerates waterlogging.",
    },
    "NRC 37 (Ahilya 4)": {
        "institution": "ICAR-IISR Indore",
        "duration_days": "98-102",
        "suitability": "Black cotton soils of Malwa",
        "traits_hi": "काली मिट्टी के लिए उपयुक्त, जड़ सड़न और कॉलर रॉट के प्रति प्रतिरोधी, उच्च तेल मात्रा (20%)।",
        "traits_en": "Recommended for deep black soils; resistant to collar rot and charcoal rot; high oil (20%).",
    },
    "RVS 2001-4": {
        "institution": "RVSKVV Gwalior",
        "duration_days": "92-96",
        "suitability": "Western MP (Mandsaur, Ratlam, Neemuch)",
        "traits_hi": "पत्ते के झुलसे (राइजोक्टोनिया) और तना मक्खी के प्रति सहनशील, मजबूत तना।",
        "traits_en": "Tolerant to Rhizoctonia aerial blight and stem fly; robust non-lodging stem.",
    },
}


def get_soybean_stage(das: int) -> dict[str, Any]:
    """Finds the current phenological growth stage of soybean given days after sowing (DAS)."""
    for stage in SOYBEAN_STAGES:
        if stage["das_min"] <= das <= stage["das_max"]:
            return stage
    if das > SOYBEAN_STAGES[-1]["das_max"]:
        return SOYBEAN_STAGES[-1]
    return SOYBEAN_STAGES[0]


def evaluate_girdle_beetle_risk(days_window: list[dict[str, Any]], das: int) -> dict[str, Any]:
    """Calculates Girdle Beetle (Obereopsis brevis) infestation risk in soybean.

    Girdle beetle attacks predominantly at 20-55 DAS. Adults girdle petioles and stems
    with twin ring cuts after alternating showers and warm sunshine (Tmean 25-30 C, RH 70-85%).
    """
    if not days_window:
        return {"score": 0.0, "band": "safe", "drivers": []}

    n = len(days_window)
    showers = sum(1 for d in days_window if 2.0 <= d.get("rain_mm", 0) <= 25.0) / n
    sun = sum(d.get("sunshine_h", 0) for d in days_window) / n
    tm = sum(d.get("tmean", 0) for d in days_window) / n

    # Phenological susceptibility window
    stage_vulnerable = 1.0 if 20 <= das <= 55 else 0.35

    temp_factor = 1.0 if 24.0 <= tm <= 30.5 else 0.4
    weather_score = 0.5 * showers + 0.3 * min(1.0, sun / 7.0) + 0.2 * temp_factor
    fused_score = round(weather_score * stage_vulnerable * 100, 1)

    drivers = [
        {
            "en": f"Soybean is at {das} DAS: prime petiole girdling and egg-laying window (20-55 DAS)",
            "hi": f"सोयाबीन {das} दिन की अवस्था में है: चक्र भृंग के अंडा देने का सर्वाधिक संवेदनशील समय",
        },
        {
            "en": f"{round(showers * n)} days with intermittent rain showers followed by bright sun favoring beetle emergence",
            "hi": f"रुक-रुक कर बारिश और धूप का संयोजन ({round(showers * n)} दिन) चक्र भृंग के उभार के अनुकूल",
        },
    ]

    return {
        "score": fused_score,
        "band": "high" if fused_score >= 70 else "watch" if fused_score >= 40 else "safe",
        "drivers": drivers,
        "scouting_tip_hi": "सुबह के समय पत्तों के डंठल और मुख्य तने पर दो गोल छल्ले (रिंग) की जांच करें। मुरझाए डंठल तुरंत तोड़ें।",
        "scouting_tip_en": "Scout petioles and main stems in the morning for twin ring cuts. Pinch and remove wilted tops immediately.",
    }


def get_soybean_profile(das: int, weather_days: list[dict[str, Any]] | None = None, variety: str = "JS 335") -> dict[str, Any]:
    """Generates complete soybean agronomic intelligence report for a farmer's field."""
    stage = get_soybean_stage(das)
    days_to_next = max(0, stage["das_max"] - das + 1)
    gb_eval = evaluate_girdle_beetle_risk(weather_days or [], das)

    var_info = MP_SOYBEAN_VARIETIES.get(variety, MP_SOYBEAN_VARIETIES["JS 335"])

    return {
        "crop": "Soybean (सोयाबीन)",
        "variety": variety,
        "variety_details": var_info,
        "das": das,
        "current_stage": {
            "code": stage["stage_code"],
            "name_en": stage["stage_name_en"],
            "name_hi": stage["stage_name_hi"],
            "description_en": stage["description_en"],
            "description_hi": stage["description_hi"],
            "water_sensitivity": stage["water_sensitivity"],
            "days_remaining_in_stage": days_to_next,
        },
        "critical_pests": stage["key_threats"],
        "etl_threshold": stage["etl"],
        "cultural_guidance": {
            "en": stage["cultural_guidance_en"],
            "hi": stage["cultural_guidance_hi"],
        },
        "foliar_nutrition": stage["foliar_nutrition"],
        "girdle_beetle_assessment": gb_eval,
        "icar_iisr_principles": [
            {
                "en": "Targeted Spot Spraying: Spray only satellite-flagged stress zones (saves 65-80% chemical).",
                "hi": "सटीक छिड़काव: केवल उपग्रह द्वारा चिह्नित तनाव पैच पर स्प्रे करें (65-80% दवा की बचत)।",
            },
            {
                "en": "Pollinator Protection: Restrict spraying during peak 10:00 AM - 03:00 PM flowering hours.",
                "hi": "मित्र कीट संरक्षण: फूल खिलने के समय सुबह 10 से दोपहर 3 बजे तक छिड़काव से बचें।",
            },
            {
                "en": "Water Volume for Drones: Ensure 20-25 L/ha with drift-reducing nozzles.",
                "hi": "ड्रोन से छिड़काव: 20-25 लीटर प्रति हेक्टेयर पानी और एंटी-ड्रिफ्ट नोजल का प्रयोग करें।",
            },
        ],
    }
