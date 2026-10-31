"""The voice menu as pure functions: (case state, step, digit) -> what to say + side effects.

The same script drives Twilio (TwiML) and the web keypad fallback, so both
always behave identically. Rules from the PRD voice design: one decision per
prompt, max 4 options, 9 repeats, 0 is a human, anything that spends money is
confirmed by a key press.
"""
from dataclasses import dataclass, field

REPEAT, HUMAN = "9", "0"
CAUSE_HI = {
    "yellow_mosaic": "peela mosaic",
    "fungal": "patton ka jhulsa",
    "chewing_damage": "illi se patton ka nuksaan",
    "water_stress": "paani ki kami ya jal bharav",
    "nutrient": "khaad ki kami",
}
QUESTIONS = [
    ("whitefly_under_leaves", "Kya patton ke neeche chhoti safed makkhiyan dikh rahi hain?"),
    ("holes_in_leaves", "Kya patton mein chhed hain ya kinaare khaaye hue hain?"),
    ("standing_water", "Kya kheth ke us hisse mein paani bhara rehta hai?"),
]


@dataclass
class Prompt:
    step: str
    say_hi: str
    options: dict[str, str] = field(default_factory=dict)
    next_step: str | None = None
    hangup: bool = False
    actions: list[str] = field(default_factory=list)       # send_link | book_didi | send_dose_sms | transfer_human
    answers: dict[str, bool] = field(default_factory=dict)


def _menu(text: str, options: dict[str, str]) -> str:
    keys = " ".join(f"{label} ke liye {k} dabaiye." for k, label in options.items())
    return f"{text} {keys} Dobara sunne ke liye 9."


def warning(case: dict) -> Prompt:
    risk = case["risk"]
    drivers = ", ".join(d["hi"] for d in risk["drivers"][:2])
    text = (f"Namaste {case['farmer_name']}. ICAR ki salah aur mausam ke hisaab se aapke khet mein "
            f"{CAUSE_HI.get(risk['cause'], risk['cause'])} ka khatra badh raha hai, kyonki {drivers}. "
            f"Satellite ne khet ke ek hisse ko kamzor dikhaya hai.")
    opts = {"1": "photo ka link", HUMAN: "expert se baat"}
    return Prompt("warning", _menu(text, opts), opts, next_step="q0")


def question(i: int) -> Prompt:
    key, text = QUESTIONS[i]
    opts = {"1": "haan", "2": "nahi"}
    return Prompt(f"q{i}", _menu(text, opts), opts, next_step=f"q{i + 1}" if i + 1 < len(QUESTIONS) else "link_sent")


def link_sent() -> Prompt:
    return Prompt("link_sent", "Dhanyavaad. Aapke phone par SMS bheja hai. Link kholiye aur awaaz ke saath kheth mein "
                               "chaliye. Photo milne ke baad hum aapko phir call karenge.", hangup=True)


def result(case: dict) -> Prompt:
    ev = case["evidence"]
    pct = round(ev["confidence"] * 100)
    cause = CAUSE_HI.get(ev["cause"], ev["cause"])
    where = f"lagbhag {case['zone_acres']:.1f} acre" if case.get("zone_acres") else "ek hisse"
    head = f"ICAR-NSRI ki salah ke anusaar, aapke khet ke {where} mein {cause} ka shak hai, {pct} pratishat."
    if ev["action"] == "advise_spray":
        spray = ev["plan"]["spray"]
        text = (f"{head} Sirf us hisse mein {spray['quantity']:.0f} {spray['unit']} dawa lagegi, poore khet mein nahi.")
        opts = {"1": "Drone Didi se spray", "2": "dawa ki jaankari SMS par", HUMAN: "expert se baat"}
    elif ev["action"] == "didi_verify":
        text = f"{head} Pakka karne ke liye Drone Didi pehle kheth dekhengi, phir zaroorat ho to spray karengi."
        opts = {"1": "Drone Didi ki jaanch", HUMAN: "expert se baat"}
    elif ev["action"] == "advise_no_pesticide":
        text = f"{head} Isme keetnashak ki zaroorat nahi hai. {ev['plan']['cultural'][0] if ev.get('plan') else ''}"
        opts = {HUMAN: "expert se baat"}
    else:
        text = f"{head} Hum aapko krishi expert se jod rahe hain."
        return Prompt("result", text, {}, hangup=True, actions=["transfer_human"])
    return Prompt("result", _menu(text, opts), opts, next_step="result_choice")


def confirm_didi(case: dict) -> Prompt:
    acres = case.get("zone_acres") or 0
    opts = {"1": "pakka karein", "2": "abhi nahi"}
    return Prompt("confirm_didi", _menu(f"Drone Didi sirf {acres:.1f} acre mein spray karengi.",
                                        opts), opts, next_step="booked")


def handle(case: dict, step: str, digit: str | None) -> Prompt:
    """Next prompt after `digit` was pressed on `step` (digit None = first time on this step)."""
    if digit is None or digit == REPEAT:
        return _render(case, step)
    if digit == HUMAN:
        return Prompt(step, "Aapko expert se jod rahe hain.", hangup=True, actions=["transfer_human"])

    if step == "warning":
        if digit == "1":
            p = question(0)
            p.actions.append("send_link")
            return p
    elif step.startswith("q") and step[1:].isdigit():
        i = int(step[1:])
        if digit in ("1", "2"):
            ans = {QUESTIONS[i][0]: digit == "1"}
            p = question(i + 1) if i + 1 < len(QUESTIONS) else link_sent()
            p.answers = ans
            return p
    elif step == "result":
        action = case["evidence"]["action"]
        if digit == "1" and action == "advise_spray":
            return confirm_didi(case)
        if digit == "1" and action == "didi_verify":
            return Prompt("booked", "Drone Didi ko bata diya hai. Woh aapko call karengi.", hangup=True,
                          actions=["book_didi"])
        if digit == "2" and action == "advise_spray":
            return Prompt("dose_sms", "Dawa aur matra SMS par bhej di hai. Dhanyavaad.", hangup=True,
                          actions=["send_dose_sms"])
    elif step == "confirm_didi":
        if digit == "1":
            return Prompt("booked", "Booking pakki. Drone Didi samay batane ke liye call karengi.", hangup=True,
                          actions=["book_didi"])
        if digit == "2":
            return Prompt("declined", "Theek hai. Zaroorat ho to humein phir call kijiye.", hangup=True)

    p = _render(case, step)                       # wrong key: repeat the same prompt
    p.say_hi = "Galat button. " + p.say_hi
    return p


def _render(case: dict, step: str) -> Prompt:
    if step == "warning":
        return warning(case)
    if step.startswith("q") and step[1:].isdigit():
        return question(int(step[1:]))
    if step == "result":
        return result(case)
    if step == "confirm_didi":
        return confirm_didi(case)
    return link_sent()
