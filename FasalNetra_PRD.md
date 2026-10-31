# FasalNetra — Product Requirements Document (Hackathon v1)

**Event:** AI Manthan 2.0, Round 2 · 24 hours · starts 31 Oct 2026
**Team:** Coder A (backend + AI) · Coder B (frontend + drone sim) · Pitcher (story, deck, clips)
**Status:** Final scope for the build. Anything not in this document is out of scope.

> **One line:** Weather tells us **when**. The farmer's traps and a guided 5-spot walk tell us **where**. Vision AI on his photos tells us **what**. The Drone Didi sprays **only the patch that is actually sick**.

---

## 1. Problem Statement

Soybean farmers in Madhya Pradesh usually find pests and disease only after leaves turn yellow, and then spray the **whole field** even when only one part is affected. In 2025, a yellow mosaic outbreak in Mandsaur led to a compensation survey on 1 Sept 2025, and India's soybean output fell from 125.82 lakh t (2024) to 105.36 lakh t (2025). Existing tools (MahaVISTAAR / Bharat-VISTAAR) answer questions at district level after the farmer notices a problem. IIT-B's iSARATHI predicts disease but needs sensors in each field. Nobody warns an individual farmer early **and** finds the sick part of his field before anyone sprays.

**Evidence:** expert interview with Dr. Savita Kolhe (ICAR-IISR): predictions must come about 15 days early; drone imaging is unreliable because rotor wind shakes the plants; farmers trust ICAR-IISR weekly advisories.

---

## 2. Goals

| # | Goal | How we know (in the demo) |
|---|---|---|
| G1 | Warn the farmer **before** symptoms, not after | Mandsaur 2025 backtest: risk score turns High **≥ 10 days** before the 1 Sept 2025 outbreak report |
| G2 | Find **where** in the field, using the farmer's own field data | Trap counts + 5-spot walk produce a zone covering **< 40%** of the field |
| G3 | Spray only the sick zone | Savings shown: litres and ₹ saved vs whole-field spray (target ≥ 60% less pesticide in the demo case) |
| G4 | Work for a low-literacy farmer | Whole loop needs only answering calls, pressing keys and taking photos. No reading, typing or app install |
| G5 | Never spray on a weak signal | No spray option is offered unless confidence is High or a human has confirmed |

---

## 3. Non-Goals

| Non-goal | Why it is out |
|---|---|
| Predicting the exact corner of a field 15 days ahead | No public data can do this. We **find** the corner with traps + the walk, at the moment of decision |
| Drone **imaging** or village survey flights | Contradicts our expert's evidence (rotor wind blur) and our pitch. The drone only sprays |
| Khasra / land-record lookup | No open API; needs a state partnership. Slide only |
| Inbound problem menu (beyond onboarding), self-spray path, Marathi | Overlaps MahaVISTAAR or adds build time without new judging value. One sentence in the pitch |
| Photos or GPS over the phone call itself | A voice call can't carry a camera or GPS. These two steps always go through the SMS link |
| Field sensors, soil card, SoilGrids, satellite wet-spot layer | Not needed for the route; sensors appear only as "plugs in" |
| Insurance proof, real drone hardware | Future |

---

## 4. Personas

- **Ramesh-ji (farmer):** 2-acre soybean field near Mandsaur, sown 40 days ago. Basic Hindi, limited reading. Smartphone shared with his son.
- **Drone Didi:** SHG member with a spray drone under the Namo Drone Didi scheme. Gets paid per acre.
- **KVK expert:** gets the case when the system is not sure.
- **Judge (demo user):** holds a verified phone and presses the keys during the live demo.

---

## 5. The One Route (end-to-end flow)

**Channel decision: IVR for onboarding and all farmer communication.** Every conversation with the farmer is a phone call with pre-recorded Hindi prompts and keypad answers. The only two things a call can't do (photos and GPS) go through an SMS link that the IVR sends during the call.

**Demo date: 15 August 2025, Mandsaur, using real historical weather.**

0. **IVR onboarding** (about 2 minutes, shown live in about 30 s): the farmer gives a missed call → the system calls back free → language → crop → sowing date → village by PIN code → landmarks for the field corners → "jaal lagaiye" (place the traps) instruction → SMS link to walk the field edge (or seeded outline / Didi task if he can't). Ramesh-ji is then registered. For the main demo he is pre-registered with the same data.
1. **Risk engine** scores the next 15 days for his field → one day turns High.
2. **Warning call** (Hindi, Twilio): "ICAR-IISR ki salah aur mausam ke hisaab se safed makkhi ka khatra… chaaron jaal ki photo bhejiye. Link ke liye 1 dabaiye." ("Following ICAR-IISR advice and the weather, whitefly risk is rising… send photos of all four traps. Press 1 for the link.")
3. **SMS link** → **trap photos** → vision AI counts whiteflies per trap → highest-count corner identified.
4. **Guided 5-spot walk:** the page sends him to 5 spots (starting near the worst trap), one GPS-tagged leaf photo each (top + underside) → vision AI scores each spot → field heat map → zone.
5. **Evidence card:** suspected cause + confidence from the weighted vote.
6. **Result call:** "ICAR-IISR ki salah ke anusaar peela mosaic ka shak, 86%, tubewell wale kone mein lagbhag 0.4 acre. Drone Didi ke liye 1." ("Following ICAR-IISR advice, yellow mosaic is suspected, 86%, in the tubewell corner, about 0.4 acre. Press 1 for Drone Didi.")
7. **Key 1 confirms the cost** → Drone Didi receives zone + route → drone animation sprays **only the zone** → ₹ and litres saved.
8. **Day +5 button** → follow-up call "Sudhaar hua? Haan 1, thoda 2, nahi 3" ("Has it improved? Yes 1, a little 2, no 3") → field turns green.

The **dashboard** shows every step live (map + event feed) on the projector.

---

## 6. User Stories

**Farmer**
0. As a new farmer, I want to register by giving a missed call and pressing keys, so that I don't need an app, a form or someone to type for me.
1. As a farmer, I want a call in Hindi before my crop shows damage, so that I can act while it is still cheap.
2. As a farmer, I want to be told *why* I am being warned and who says so (ICAR-IISR), so that I can trust the call.
3. As a farmer, I want a phone page that tells me by voice where to walk and what to photograph, so that I don't need to read.
4. As a farmer, I want to know which part of my field is sick, in my own landmarks ("tubewell wala kona", the tubewell corner), so that I don't spray the whole field.
5. As a farmer, I want to confirm any cost by pressing a key, so that nothing is booked by mistake.
6. As a farmer, I want to hear how much money and pesticide I saved, so that I see the value.
7. *Edge:* As a farmer whose photo is blurry, I want to be asked to retake it, so that the diagnosis isn't wrong.
8. *Edge:* As a farmer, when the system is not sure, I want to be connected to a human expert instead of being told to spray.

**Drone Didi**
9. As a Drone Didi, I want the exact zone and route for the farm, so that I spray only what is needed and save battery.

**Judge**
10. As a judge, I want to press keys on a real phone and watch each step appear on screen, so that I can see the system is working.

---

## 7. Requirements

### P0 — Must have (the demo fails without these)

**IVR rules (apply to every call)**
- Pre-recorded Hindi MP3s for fixed prompts, one local voice; numbers and names inserted with Indian TTS only where needed.
- One question per prompt, at most 4 options. **9 = repeat**, **0 = talk to a human**.
- 8-second timeout → repeat once → polite exit, event logged, retry call after 2 h.
- Anything that costs money is confirmed by a key press, never by speech.
- Every call and key press is written to the dashboard event feed.

**P0-0 · IVR onboarding** (Coder A, prompts by Pitcher)
- Missed call (or inbound call) → hang up → free callback within 30 s.
- Menu sequence: language (Hindi 1, Marathi 2 — demo plays Hindi only) → crop (Soybean 1, Makka 2, Urad 3, Kuch aur 4; "Makka" = maize, "Kuch aur" = something else) → sowing date (under 15 days 1, 15–30 2, 30–60 3, over 60 4) → **village by 6-digit PIN code** on the keypad, then the matching villages read out as 1/2/3 → field corner landmarks (Tubewell 1, Sadak 2, Nala 3, Ped 4, Ghar 5; that is tubewell, road, stream, tree, house) → neighbouring crop (Urad/Moong 1, Soybean 2, Kuch aur 3) → grass on the border (Haan 1, Nahi 2).
- Ends with: trap instructions + SMS link to walk the field edge. No smartphone → outline is a Didi task (demo: seeded outline).
- Acceptance:
  - [ ] A verified phone gives a missed call and receives the callback within 30 s
  - [ ] All answers are saved to the farmer record and shown on the dashboard
  - [ ] Wrong or no key → prompt repeats once, then moves on with "pata nahi" ("don't know") saved
  - [ ] Registration finishes in ≤ 2 minutes when answered promptly
  - [ ] Fallback: a web keypad page runs the same menus against the same endpoints

**P0-1 · Risk engine** (Coder A)
- Inputs: Open-Meteo hourly archive for Mandsaur (Jun–Sep 2025), crop stage from sowing date, ICAR-IISR advisory flag.
- Leaf-wetness hours = hours with humidity ≥ 90%.
- Rule: the published MP yellow-mosaic weather rule (Tmax > 33°C, sunshine/temperature raise risk; rain and evening humidity lower it; exact thresholds from the paper), plus crop stage 30–60 days = vulnerable.
- Output per day: score 0–100, band (Safe < 40, Watch 40–70, High ≥ 70), top 3 drivers in plain words.
- Acceptance:
  - [ ] Given the demo date 15 Aug 2025, the engine returns 15 daily scores in < 2 s
  - [ ] At least one day is High, with drivers listed
  - [ ] Backtest script prints the first High date before 1 Sept 2025 and the number of days early

**P0-2 · Outbound warning call + keypad** (Coder A)
- Twilio call with pre-recorded Hindi MP3s; `<Gather numDigits=1>`; key press posted to the backend.
- Acceptance:
  - [ ] Pressing "Call" on the dashboard rings a verified phone within 10 s
  - [ ] Key press appears in the dashboard event feed within 1 s
  - [ ] No key press → retry message once, then the call ends politely and the event is logged
  - [ ] Fallback: a web keypad hits the same endpoint

**P0-3 · SMS link + trap photo count** (Coder A + B)
- SMS with link → page asks for 4 trap photos (one per corner, labelled by the farmer's landmarks).
- Vision AI returns whitefly count per trap as JSON.
- Acceptance:
  - [ ] Each photo returns a count within 5 s
  - [ ] Highest-count corner is shown and used as the walk's starting point
  - [ ] Blurry or dark photo → "phir se lijiye" ("please retake") with audio prompt

**P0-4 · Guided 5-spot walk** (Coder B + A)
- Voice-guided page: 5 spots in a W pattern, starting near the worst trap; at each spot, leaf top + underside photo with GPS.
- Vision AI per spot: symptom (yellow mosaic / chewing damage / fungal / healthy), severity 0–3, whitefly presence.
- Zone = area around spots with severity ≥ 2.
- Acceptance:
  - [ ] Works on a mid-range Android in Chrome, big buttons, Hindi audio per step
  - [ ] Heat map and zone appear on the dashboard as each spot is submitted
  - [ ] Fallback: pre-recorded GPS walk + sample photos if indoors GPS drifts

**P0-5 · Evidence card + confidence** (Coder A + B)
- Weighted vote: photo AI 3 (halved if blurry), trap counts 2, keypad answers 2, weather fit 2, crop stage 1, IISR advisory 1.
- Confidence = votes for top cause ÷ all votes. High ≥ 75% (needs at least one field signal) · Medium 50–75% · Low < 50%.
- Card shows: cause, confidence ring, band colour, one bar per signal, zone thumbnail, source line "ICAR-IISR advisory, week of …".
- Acceptance:
  - [ ] Demo case reaches High with ≥ 3 agreeing signals
  - [ ] Medium/Low hides the spray button and shows "Expert se baat" ("Talk to an expert")
  - [ ] The word used is always "shak" / "suspected", never a certain diagnosis

**P0-6 · Result call + Drone Didi booking** (Coder A)
- Result call with cause, confidence, zone in landmarks, source; key 1 confirms the cost.
- Acceptance:
  - [ ] Cost is confirmed only by key press
  - [ ] Booking event sends zone + route to the "Didi" view

**P0-7 · Zone-only spray route + savings** (Coder B)
- Lawnmower route over the zone (shapely), exported as `.waypoints`; animated drone on the map.
- Savings: litres = (field area − zone area) × dose/acre; ₹ = litres × price. Dose and price from a real label and shop.
- Acceptance:
  - [ ] Drone path never leaves the zone (+ small buffer)
  - [ ] Counter shows litres, ₹ and acres not sprayed

**P0-8 · Live dashboard** (Coder B)
- Map (left) + event feed (right) + top strip (farmer, crop, stage, today's band); WebSocket events.
- Hidden key resets the demo to the seeded state.
- Acceptance:
  - [ ] Readable on a projector (≥ 18 px text, same green/yellow/red everywhere)
  - [ ] Full demo runs from reset to Day +5 without typing

### P1 — Nice to have (only if P0 works at H16, in this order)
1. **Day +5 follow-up button** (follow-up call + field turns green). *Treat as near-P0; about 30 min.*
2. **Neighbour warnings:** 3 seeded fields turn Watch after the confirmed case.
3. **Edge exposure line** on the evidence card (neighbouring urad/moong, grassy border, upwind of a case) from seeded onboarding answers.
4. **Sentinel-2 layer:** one prepared image of the demo field.
5. **15-day heat map autoplay** on the dashboard.
6. **ArduPilot SITL** running the same `.waypoints` (only if it works on the laptop).

### P2 — Future (slides; design so these fit later)
- Village-level warnings to unregistered farmers via FPO / SHG / KVK lists; khasra lookup via AgriStack with consent.
- Hindi speech recognition for village names (keypad PIN code is used in v1).
- Inbound call menu, self-spray guidance, Marathi.
- Sensor input endpoint (iSARATHI-style), satellite wet-spot layer, Sentinel-1 radar for monsoon clouds.
- Kisan Call Centre spike data (AIKosh) feeding the area-level risk.
- Integration as a layer on MahaVISTAAR / Bharat-VISTAAR.

---

## 8. Data

| Data | Source | Used in |
|---|---|---|
| Hourly weather, Mandsaur, 1 Jun–15 Sep 2025 | Open-Meteo archive API | P0-1, backtest |
| MP yellow-mosaic weather rule | ICAR KRISHI / IJBB paper | P0-1 |
| Soybean leaf photos (mosaic, healthy, chewing damage) | MH-SoyaHealthVision, SoyNet (CC BY 4.0) | Testing P0-4, stage backup |
| Yellow sticky trap photos | Kaggle whitefly trap set or home-made card | P0-3 |
| ICAR-IISR advisory, Aug 2025 | ICAR-IISR | Source line, product |
| Pesticide label + local price | Label / Indore shop | P0-7 savings |
| Field outlines (Ramesh-ji + 3 neighbours) | geojson.io | Map, zone, P1-2 |

**Contract (agreed at H0):** `Field`, `Risk`, `Signal`, `Evidence`, `Mission`, `Event` JSON shapes as in the game plan.

---

## 9. Success Metrics

**Demo (judged on 1 Nov)**

| Metric | Target |
|---|---|
| Full loop, call to spray, completes live | 100% in all 3 rehearsals |
| Backtest lead time | High ≥ 10 days before 1 Sept 2025 (stretch: 15) |
| Key press → on screen | ≤ 1 s |
| Photo → AI result | ≤ 5 s |
| Pesticide saved in demo case | ≥ 60% vs whole field |
| Photo AI check on ~100 SoyNet / MH-SoyaHealthVision images | Report the agreement % honestly, whatever it is |

**Pilot (after the hackathon: 1 Drone Didi, 10 farmers, 1 season)**

| Leading | Lagging |
|---|---|
| % warning calls answered (target 70%) | Pesticide litres per acre vs last season |
| % farmers sending trap photos when asked (target 50%) | Yield loss vs neighbouring non-users |
| % "nahi dikha" ("didn't see it") replies, i.e. false alarms (watch, tune threshold) | Repeat use next season |

---

## 10. Open Questions

| Question | Owner | Blocking? |
|---|---|---|
| Exact thresholds of the MP yellow-mosaic rule, including the humidity cutoff | Coder A (read the paper) | **Yes** for P0-1. Fallback: provisional thresholds, labelled as such |
| PIN code → village list for the demo area (a small table of Mandsaur PIN codes and villages) | Coder A | Yes for P0-0. Fallback: a seeded table for 1 PIN code |
| Does a Twilio trial number accept missed calls and call back Indian verified numbers reliably from the venue? | Coder A (test tonight) | Yes for P0-0. Fallback: web keypad page |
| Which product does the Aug 2025 IISR advisory recommend for whitefly, and its dose per acre? | Pitcher | Yes for P0-7 numbers |
| Licence of the Kaggle trap dataset, or do we use our own card photos? | Coder A | No |
| Does the backtest actually turn High before 1 Sept 2025? If not, how do we present it honestly? | Coder A + Pitcher | No, but decides a pitch slide |
| Does ArduPilot SITL run on the demo laptop? | Coder B | No |
| Can the interviewed farmer get a recorded test call? | Pitcher | No |
| Length of the presentation slot | Pitcher | No (run of show scales) |

---

## 11. Timeline

| Hours | Milestone |
|---|---|
| H0–1 | Repo, contract, seed data, tunnel, Twilio test call |
| H1–3 | All steps on stub data; dashboard clicks through the story |
| H3–6 | P0-2 real call + event feed; IVR rules and shared call engine |
| H6–8 | P0-0 IVR onboarding (reuses the same call engine) |
| H6–12 | P0-3, P0-4, P0-5, P0-6 |
| **H12** | **Checkpoint: whole loop once on a real phone.** If not, cut P1 entirely |
| H12–16 | P0-1 real risk engine + backtest, P0-7 polish |
| H16–19 | P1 items in order; polish |
| **H19–20** | **Feature freeze; record backup video** |
| H20–24 | Bug fixes only; rehearse 3×; Q&A drill |

**Cut order if late:** P1 (all) → onboarding shortened to crop + sowing date only (rest seeded) → trap-count step merges into the walk (walk starts at spot 1) → edge cases. **Never cut:** warning call, photos, evidence card, zone-only spray.

---

## 12. Pitch Positioning (for consistency)

- "MahaVISTAAR and Bharat-VISTAAR answer questions with official advice. FasalNetra warns first, finds the sick patch from the farmer's own field data, and makes every Drone Didi flight count."
- "Why not just fly a drone over every field?" slide: image blur from rotor wind (Dr. Kolhe), damage already visible by then, battery and scale limits, and the rules on flying beyond the pilot's sight.
- Words to use: "suspected", "confidence score", "we consulted ICAR-IISR", "simulated in ArduPilot". Never: "99% accurate", "ICAR endorses", "India's first", "MahaVISTAAR is weak".
