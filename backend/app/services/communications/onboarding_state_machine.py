"""FasalNetra IVR Onboarding State Machine

Deterministic state machine handling farmer registration via phone keypad.
Follows PRD rules: 8-second timeout, 1 reprompt, 9 to repeat, no 0 human transfer.
"""

from typing import Any
from backend.app.data.pincodes import get_villages_for_pincode

# Step definitions
STEPS = [
    "welcome",
    "crop",
    "sowing_date",
    "pincode",
    "village",
    "neighbor_crop",
    "grass_border",
    "completed",
]

# Choice mappings for each step
CHOICE_MAP: dict[str, dict[str, str]] = {
    "welcome": {
        "1": "hi",
        "2": "mr",
    },
    "crop": {
        "1": "soybean",
        "2": "maize",
        "3": "urad",
        "4": "other",
    },
    "sowing_date": {
        "1": "under_15",
        "2": "15_30",
        "3": "30_60",
        "4": "over_60",
    },
    "neighbor_crop": {
        "1": "urad_moong",
        "2": "soybean",
        "3": "other",
    },
    "grass_border": {
        "1": "yes",
        "2": "no",
    },
}


def get_step_config(step: str, answers: dict[str, Any]) -> dict[str, Any]:
    """Return prompt text, audio prompt ID, and input expectations for a step."""
    if step == "welcome":
        return {
            "step": "welcome",
            "prompt_id": "onboarding_01_welcome",
            "prompt_text": "फसलनेत्र में आपका स्वागत है। हिंदी के लिए 1 दबाएं, मराठी के लिए 2 दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": ["1", "2"],
            "options": [
                {"digit": "1", "label": "हिंदी (Hindi)"},
                {"digit": "2", "label": "मराठी (Marathi)"},
            ],
        }

    elif step == "crop":
        return {
            "step": "crop",
            "prompt_id": "onboarding_02_crop",
            "prompt_text": "अपनी मुख्य फसल चुनें। सोयाबीन के लिए 1, मक्का के लिए 2, उड़द के लिए 3, या अन्य फसल के लिए 4 दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": ["1", "2", "3", "4"],
            "options": [
                {"digit": "1", "label": "सोयाबीन (Soybean)"},
                {"digit": "2", "label": "मक्का (Maize)"},
                {"digit": "3", "label": "उड़द (Urad)"},
                {"digit": "4", "label": "अन्य (Other)"},
            ],
        }

    elif step == "sowing_date":
        return {
            "step": "sowing_date",
            "prompt_id": "onboarding_03_sowing",
            "prompt_text": "बोवनी को कितने दिन हुए हैं? 15 दिन से कम के लिए 1, 15 से 30 दिन के लिए 2, 30 से 60 दिन के लिए 3, या 60 दिन से ज्यादा के लिए 4 दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": ["1", "2", "3", "4"],
            "options": [
                {"digit": "1", "label": "< 15 दिन"},
                {"digit": "2", "label": "15-30 दिन"},
                {"digit": "3", "label": "30-60 दिन"},
                {"digit": "4", "label": "> 60 दिन"},
            ],
        }

    elif step == "pincode":
        return {
            "step": "pincode",
            "prompt_id": "onboarding_04_pincode",
            "prompt_text": "कृपया अपने क्षेत्र का 6 अंकों का पिन कोड कीपैड पर दर्ज करें। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 6,
            "valid_digits": None,  # Accepts any 6-digit number
            "options": [],
        }

    elif step == "village":
        pincode = answers.get("pincode", "458001")
        villages = get_villages_for_pincode(pincode)
        valid_digits = [v["digit"] for v in villages]

        village_prompt_parts = []
        for v in villages:
            village_prompt_parts.append(f"{v['name']} के लिए {v['digit']}")
        village_prompt_str = ", ".join(village_prompt_parts)

        return {
            "step": "village",
            "prompt_id": f"onboarding_05_village_{pincode}",
            "prompt_text": f"अपना गांव चुनें। {village_prompt_str} दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": valid_digits,
            "options": [{"digit": v["digit"], "label": v["name"]} for v in villages],
        }

    elif step == "neighbor_crop":
        return {
            "step": "neighbor_crop",
            "prompt_id": "onboarding_07_neighbor",
            "prompt_text": "आस-पास के खेत में कौन सी फसल है? उड़द या मूंग के लिए 1, सोयाबीन के लिए 2, या कुछ और के लिए 3 दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": ["1", "2", "3"],
            "options": [
                {"digit": "1", "label": "उड़द / मूंग"},
                {"digit": "2", "label": "सोयाबीन"},
                {"digit": "3", "label": "कुछ और"},
            ],
        }

    elif step == "grass_border":
        return {
            "step": "grass_border",
            "prompt_id": "onboarding_08_grass",
            "prompt_text": "क्या खेत की मेड़ पर घास या खरपतवार है? हां के लिए 1, नहीं के लिए 2 दबाएं। दोबारा सुनने के लिए 9 दबाएं।",
            "num_digits": 1,
            "valid_digits": ["1", "2"],
            "options": [
                {"digit": "1", "label": "हां (Yes)"},
                {"digit": "2", "label": "नहीं (No)"},
            ],
        }

    elif step == "completed":
        return {
            "step": "completed",
            "prompt_id": "onboarding_09_completed",
            "prompt_text": "धन्यवाद! आपका पंजीकरण पूरा हो गया है। कृपया अपने खेत के चारों कोनों पर पीले चिपचिपे जाल लगाएं। खेत की सीमा दर्ज करने के लिए आपके फोन पर SMS लिंक भेजा गया है।",
            "num_digits": 0,
            "valid_digits": [],
            "options": [],
        }

    raise ValueError(f"Unknown step: {step}")


def process_step_input(
    current_step: str,
    digits: str | None,
    current_answers: dict[str, Any],
    reprompt_count: int = 0,
) -> dict[str, Any]:
    """Processes farmer keypad input for the current step.

    Returns:
        {
            "next_step": str,
            "reprompt": bool,
            "reprompt_count": int,
            "updated_answers": dict,
            "message": str
        }
    """
    clean_digits = str(digits).strip() if digits is not None else ""
    answers = dict(current_answers)
    step_cfg = get_step_config(current_step, answers)

    # 1. Farmer pressed 9 (Repeat Prompt)
    if clean_digits == "9":
        return {
            "next_step": current_step,
            "reprompt": True,
            "reprompt_count": reprompt_count,
            "updated_answers": answers,
            "message": "Prompt repeated.",
        }

    # 2. Handle Pincode (6 digits expected)
    if current_step == "pincode":
        if len(clean_digits) == 6 and clean_digits.isdigit():
            answers["pincode"] = clean_digits
            return {
                "next_step": "village",
                "reprompt": False,
                "reprompt_count": 0,
                "updated_answers": answers,
                "message": f"Pincode {clean_digits} recorded.",
            }
        # Timeout or invalid pincode
        if reprompt_count < 1:
            return {
                "next_step": "pincode",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "updated_answers": answers,
                "message": "कृपया 6 अंकों का सही पिन कोड दर्ज करें।",
            }
        else:
            # Fallback to default demo pincode if repeated failure
            answers["pincode"] = "458001"
            return {
                "next_step": "village",
                "reprompt": False,
                "reprompt_count": 0,
                "updated_answers": answers,
                "message": "Default pincode 458001 applied.",
            }

    # 3. Handle Village Selection
    if current_step == "village":
        pincode = answers.get("pincode", "458001")
        villages = get_villages_for_pincode(pincode)
        valid_map = {v["digit"]: v["name"] for v in villages}

        if clean_digits in valid_map:
            answers["village"] = valid_map[clean_digits]
            return {
                "next_step": "neighbor_crop",
                "reprompt": False,
                "reprompt_count": 0,
                "updated_answers": answers,
                "message": f"Village {valid_map[clean_digits]} recorded.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "village",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "updated_answers": answers,
                "message": "कृपया सूची में से सही विकल्प चुनें।",
            }
        else:
            # Fallback to first village
            answers["village"] = villages[0]["name"]
            return {
                "next_step": "neighbor_crop",
                "reprompt": False,
                "reprompt_count": 0,
                "updated_answers": answers,
                "message": "Default village selected.",
            }

    # 4. Standard Choice Steps (1-4 or 1-5)
    valid_choices = CHOICE_MAP.get(current_step, {})
    if clean_digits in valid_choices:
        answers[current_step] = valid_choices[clean_digits]
        # Determine next step
        idx = STEPS.index(current_step)
        next_step = STEPS[idx + 1] if idx + 1 < len(STEPS) else "completed"
        return {
            "next_step": next_step,
            "reprompt": False,
            "reprompt_count": 0,
            "updated_answers": answers,
            "message": f"{current_step} recorded as {valid_choices[clean_digits]}.",
        }

    # Invalid input or timeout (empty input)
    if reprompt_count < 1:
        return {
            "next_step": current_step,
            "reprompt": True,
            "reprompt_count": reprompt_count + 1,
            "updated_answers": answers,
            "message": "कृपया दिए गए विकल्पों में से एक बटन दबाएं।",
        }
    else:
        # Default fallback after 1 reprompt
        answers[current_step] = "pata_nahi"
        idx = STEPS.index(current_step)
        next_step = STEPS[idx + 1] if idx + 1 < len(STEPS) else "completed"
        return {
            "next_step": next_step,
            "reprompt": False,
            "reprompt_count": 0,
            "updated_answers": answers,
            "message": f"{current_step} recorded as pata_nahi.",
        }
