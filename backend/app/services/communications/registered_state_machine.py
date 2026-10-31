"""FasalNetra Registered Farmer IVR State Machine

Handles call interactions for already-registered farmers based on their farm state.
Implements:
  1. Safe Reassurance (Field healthy, 0 alerts)
  2. P0-2 Outbound High-Risk Warning & SMS Dispatch
  3. P0-6 Diagnosis Result & Drone Didi Booking Confirmation
  4. Day +5 Post-Spray Outcome Follow-Up
"""

from typing import Any

from backend.app.core.config import settings

# Farmer-initiated report (missed call -> callback): key -> symptom answer id read by the evidence card
REPORT_SYMPTOMS = {
    "1": "yellow_mosaic_patches",   # पत्तों पर पीले-हरे धब्बे
    "2": "holes_in_leaves",         # पत्तों में छेद या इल्ली
    "3": "brown_spots",             # पत्तों पर भूरे धब्बे
    "4": "wilting_afternoon",       # पौधे मुरझा रहे हैं
}


def _result_prompt(context: dict[str, Any]) -> dict[str, Any]:
    """Result call built from the farmer's case evidence (see services/cases.result_context)."""
    where = f"लगभग {context['acres']:.1f} एकड़ हिस्से" if context.get("acres") else "एक हिस्से"
    head = (f"नमस्ते! ICAR-NSRI की सलाह और फोटो जांच के अनुसार आपके खेत के {where} में "
            f"{context['pct']} प्रतिशत {context['name_hi']} का शक है।")
    cfg = {"step": "result_prompt", "prompt_id": f"p06_result_{context['action']}"}
    if context["action"] == "advise_spray":
        spray = context.get("spray")
        dose = f" सिर्फ उसी हिस्से में {spray['quantity']:g} {spray['unit']} दवा लगेगी, पूरे खेत में नहीं।" if spray else ""
        text = f"{head}{dose} ड्रोन दीदी छिड़काव बुक करने के लिए 1 दबाइए। दोबारा सुनने के लिए 9 दबाइए।"
    elif context["action"] == "didi_verify":
        # Not sure yet: no percentage, just the suspicion and the offer to send Drone Didi
        text = (f"नमस्ते! आपकी फोटो मिल गई। आपके खेत के {where} में {context['name_hi']} का शक है, पर अभी पक्का नहीं कह सकते। "
                "अभी दवा मत डालिए। ड्रोन दीदी आकर खेत देखेंगी, फिर ज़रूरत हो तो सिर्फ उसी हिस्से में छिड़काव करेंगी। "
                "ड्रोन दीदी से जुड़ने के लिए 1 दबाइए। दोबारा सुनने के लिए 9 दबाइए।")
    else:   # advise_no_pesticide / expert_check: nothing to book
        return {**cfg, "prompt_text": f"{head} इसमें कीटनाशक की ज़रूरत नहीं है। हमारे कृषि विशेषज्ञ आपको जल्द कॉल करेंगे। धन्यवाद।",
                "num_digits": 0, "valid_digits": [], "hangup": True}
    return {**cfg, "prompt_text": text, "num_digits": 1, "valid_digits": ["1"], "hangup": False}


def get_registered_flow_config(flow: str, step: str, farmer: Any = None,
                               context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Returns prompt configuration, audio prompt IDs, and gather settings for registered flows.

    context: the farmer's case result (cause, confidence, zone, dose). Without it the result call
    falls back to the fixed demo script.
    """
    farmer_name = getattr(farmer, "name", "किसान भाई") if farmer else "किसान भाई"

    # ==========================================
    # 1. SAFE FLOW (Field is healthy)
    # ==========================================
    if flow == "safe":
        return {
            "step": "safe_message",
            "prompt_id": "registered_safe_reassurance",
            "prompt_text": f"नमस्ते! फसलनेत्र में आपका स्वागत है। आपके खेत में अभी कोई कीट या बीमारी का खतरा नहीं है। मौसम सामान्य है। कोई भी समस्या दिखने पर हम आपको तुरंत कॉल करेंगे। धन्यवाद।",
            "num_digits": 0,
            "valid_digits": [],
            "hangup": True,
        }

    # ==========================================
    # 1b. REPORT FLOW (farmer gave a missed call about a problem)
    # ==========================================
    elif flow == "report" and step == "report_prompt":
        return {
            "step": "report_prompt",
            "prompt_id": "report_symptom_menu",
            "prompt_text": "नमस्ते! फसलनेत्र में आपका स्वागत है। खेत में क्या दिख रहा है? पत्तों पर पीले धब्बे हैं तो 1, पत्तों में छेद या इल्ली है तो 2, पत्तों पर भूरे धब्बे हैं तो 3, पौधे मुरझा रहे हैं तो 4 दबाइए। दोबारा सुनने के लिए 9 दबाइए।",
            "num_digits": 1,
            "valid_digits": list(REPORT_SYMPTOMS),
            "hangup": False,
        }

    # ==========================================
    # 2. WARNING FLOW (P0-2 Whitefly Alert)
    # ==========================================
    elif flow in ("warning", "report"):
        if step == "warning_prompt":
            return {
                "step": "warning_prompt",
                "prompt_id": "p02_warning_call",
                "prompt_text": "नमस्ते! ICAR-IISR की सलाह और मौसम के हिसाब से आपके खेत में सफेद मक्खी का खतरा बढ़ रहा है। चारों कोनों के जालों की फोटो भेजिए। फोटो लिंक के लिए 1 दबाइए। दोबारा सुनने के लिए 9 दबाइए।",
                "num_digits": 1,
                "valid_digits": ["1"],
                "hangup": False,
            }
        elif step == "whitefly_question":
            # One field question while the farmer is on the line; the answer is a keypad signal for the evidence card
            return {
                "step": "whitefly_question",
                "prompt_id": "p02_whitefly_question",
                "prompt_text": f"फोटो का लिंक {settings.link_channel_hi} से भेज दिया है। एक सवाल: क्या पत्तों के नीचे छोटी सफेद मक्खियां दिख रही हैं? हां के लिए 1, नहीं के लिए 2 दबाइए। दोबारा सुनने के लिए 9 दबाइए।",
                "num_digits": 1,
                "valid_digits": ["1", "2"],
                "hangup": False,
            }
        elif step == "sms_dispatched":
            # Live hold: the call stays on while the farmer opens the link; /ivr/live speaks progress and the result
            return {
                "step": "sms_dispatched",
                "prompt_id": "p02_live_hold",
                "prompt_text": f"धन्यवाद! आपके फोन पर {settings.link_channel_hi} में एक लिंक आया है, उसे दबाइए। कॉल मत काटिए, फोन स्पीकर पर रखिए। "
                               "कैमरा खुलेगा, लाल लाइन के साथ चलकर बीमार पत्तों की फोटो लीजिए। फोटो आते ही मैं यहीं बताऊंगी।",
                "num_digits": 0,
                "valid_digits": [],
                "hangup": False,
                "live": True,
            }

    # ==========================================
    # 3. RESULT FLOW (P0-6 Diagnosis & Drone Booking)
    # ==========================================
    elif flow == "result":
        if step == "result_prompt" and context:
            return _result_prompt(context)
        if step == "result_prompt":
            return {
                "step": "result_prompt",
                "prompt_id": "p06_result_call",
                "prompt_text": "नमस्ते! ICAR-IISR की सलाह और फोटो जांच के अनुसार आपके खेत में 86 प्रतिशत पीले मोज़ेक का शक है, लगभग 0.4 एकड़ में। ड्रोन दीदी छिड़काव बुक करने के लिए 1 दबाइए। दोबारा सुनने के लिए 9 दबाइए।",
                "num_digits": 1,
                "valid_digits": ["1"],
                "hangup": False,
            }
        elif step == "booking_confirmed" and context and context["action"] == "didi_verify":
            return {
                "step": "booking_confirmed",
                "prompt_id": "p06_verify_booked",
                "prompt_text": "धन्यवाद! ड्रोन दीदी को बता दिया है। वे आकर आपका खेत देखेंगी और ज़रूरत हो तो सिर्फ बीमार हिस्से में छिड़काव करेंगी।",
                "num_digits": 0,
                "valid_digits": [],
                "hangup": True,
            }
        elif step == "booking_confirmed":
            return {
                "step": "booking_confirmed",
                "prompt_id": "p06_booking_confirmed",
                "prompt_text": "धन्यवाद! ड्रोन दीदी की बुकिंग पक्की हो गई है। ड्रोन दीदी जल्द ही आपके खेत के प्रभावित हिस्से पर छिड़काव के लिए पहुंचेगी।",
                "num_digits": 0,
                "valid_digits": [],
                "hangup": True,
            }

    # ==========================================
    # 4. FOLLOW-UP FLOW (Day +5 Recovery Verification)
    # ==========================================
    elif flow == "followup":
        if step == "followup_prompt":
            return {
                "step": "followup_prompt",
                "prompt_id": "p11_followup_call",
                "prompt_text": "नमस्ते! ड्रोन छिड़काव के बाद क्या आपकी फसल में सुधार हुआ है? हां के लिए 1, थोड़े सुधार के लिए 2, नहीं के लिए 3 दबाइए। दोबारा सुनने के लिए 9 दबाइए।",
                "num_digits": 1,
                "valid_digits": ["1", "2", "3"],
                "hangup": False,
            }
        elif step == "followup_recorded":
            return {
                "step": "followup_recorded",
                "prompt_id": "p11_followup_recorded",
                "prompt_text": "धन्यवाद! आपकी प्रतिक्रिया दर्ज कर ली गई है। फसलनेत्र से जुड़े रहने के लिए धन्यवाद।",
                "num_digits": 0,
                "valid_digits": [],
                "hangup": True,
            }

    raise ValueError(f"Unknown registered flow or step: flow={flow}, step={step}")


def process_registered_step_input(
    flow: str,
    current_step: str,
    digits: str | None,
    reprompt_count: int = 0,
) -> dict[str, Any]:
    """Processes keypad input for registered farmer flows."""
    clean_digits = str(digits).strip() if digits is not None else ""

    # Press 9 to repeat
    if clean_digits == "9":
        return {
            "next_step": current_step,
            "reprompt": True,
            "reprompt_count": reprompt_count,
            "action": "repeat",
            "message": "Prompt repeated.",
        }

    # Flow 1b: Report (farmer-initiated). Any symptom sends the photo link, then the whitefly question.
    if flow == "report" and current_step == "report_prompt":
        if clean_digits in REPORT_SYMPTOMS:
            return {
                "next_step": "whitefly_question",
                "reprompt": False,
                "reprompt_count": 0,
                "action": f"report_symptom_{REPORT_SYMPTOMS[clean_digits]}",
                "message": f"Symptom reported: {REPORT_SYMPTOMS[clean_digits]}; SMS link dispatched.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "report_prompt",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "action": "reprompt",
                "message": "कृपया 1, 2, 3 या 4 में से एक बटन दबाएं।",
            }
        return {
            "next_step": "whitefly_question",
            "reprompt": False,
            "reprompt_count": 0,
            "action": "report_symptom_unknown",   # no answer: still send the photo link
            "message": "No symptom chosen; SMS link dispatched.",
        }

    # Flow 2: Warning
    if flow == "warning" and current_step == "warning_prompt":
        if clean_digits == "1":
            return {
                "next_step": "whitefly_question",
                "reprompt": False,
                "reprompt_count": 0,
                "action": "send_sms_link",
                "message": "Key 1 pressed: SMS link dispatched.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "warning_prompt",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "action": "reprompt",
                "message": "कृपया लिंक प्राप्त करने के लिए 1 दबाएं।",
            }
        return {
            "next_step": "whitefly_question",
            "reprompt": False,
            "reprompt_count": 0,
            "action": "send_sms_link",
            "message": "Defaulting to SMS link dispatch.",
        }

    if flow in ("warning", "report") and current_step == "whitefly_question":
        if clean_digits in ["1", "2"]:
            answer = "yes" if clean_digits == "1" else "no"
            return {
                "next_step": "sms_dispatched",
                "reprompt": False,
                "reprompt_count": 0,
                "action": f"record_whitefly_{answer}",
                "message": f"Whitefly under leaves: {answer}.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "whitefly_question",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "action": "reprompt",
                "message": "कृपया हां के लिए 1 या नहीं के लिए 2 दबाएं।",
            }
        return {
            "next_step": "sms_dispatched",
            "reprompt": False,
            "reprompt_count": 0,
            "action": "record_whitefly_unknown",   # PRD: no answer -> move on with "pata nahi"
            "message": "No answer; saved as don't know.",
        }

    # Flow 3: Result & Drone Booking
    if flow == "result" and current_step == "result_prompt":
        if clean_digits == "1":
            return {
                "next_step": "booking_confirmed",
                "reprompt": False,
                "reprompt_count": 0,
                "action": "confirm_drone_booking",
                "message": "Key 1 pressed: Drone booking confirmed.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "result_prompt",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "action": "reprompt",
                "message": "कृपया बुकिंग की पुष्टि के लिए 1 दबाएं।",
            }
        return {
            "next_step": "booking_confirmed",
            "reprompt": False,
            "reprompt_count": 0,
            "action": "exit",
            "message": "No key pressed. Exiting.",
        }

    # Flow 4: Followup
    if flow == "followup" and current_step == "followup_prompt":
        if clean_digits in ["1", "2", "3"]:
            feedback_map = {"1": "yes_improved", "2": "slightly_improved", "3": "not_improved"}
            return {
                "next_step": "followup_recorded",
                "reprompt": False,
                "reprompt_count": 0,
                "action": f"record_feedback_{feedback_map[clean_digits]}",
                "message": f"Feedback {feedback_map[clean_digits]} recorded.",
            }
        if reprompt_count < 1:
            return {
                "next_step": "followup_prompt",
                "reprompt": True,
                "reprompt_count": reprompt_count + 1,
                "action": "reprompt",
                "message": "कृपया 1, 2, या 3 में से एक बटन दबाएं।",
            }
        return {
            "next_step": "followup_recorded",
            "reprompt": False,
            "reprompt_count": 0,
            "action": "record_feedback_unknown",
            "message": "Exiting follow-up.",
        }

    return {
        "next_step": "completed",
        "reprompt": False,
        "reprompt_count": 0,
        "action": "none",
        "message": "Completed.",
    }
