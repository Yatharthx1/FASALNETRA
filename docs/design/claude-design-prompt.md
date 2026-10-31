# Claude Design brief: FasalNetra

Paste everything below the line into Claude Design in one message. Part 2 condenses the rules from the project skills `frontend-design-direction`, `make-interfaces-feel-better`, `landing-page-design` (visual system only) and `frontend-a11y`. Claude Design does not load SKILL.md files, so the rules are written out.

---

## Part 1: What to design

Design a 4-surface product called FasalNetra ("crop eye") for soybean farmers in Mandsaur, Madhya Pradesh, India. It finds the sick patch of a field, confirms it with the farmer, and sends a woman drone operator ("Drone Didi") to spray only that patch.

**Users and constraints**
- Farmer: low literacy, Hindi only, mid-range Android in Chrome, outdoors in harsh sunlight, one hand free. Opens the page from an SMS link after a phone call. Never needs to read: every step has a big play-audio button, icons and photos, and a green/yellow/red colour. Tap targets at least 56 px, one action per screen, no English, no typing.
- Drone Didi: a trained woman from a self-help group, semi-literate, Hindi plus simple numbers, Android phone or tablet in the field. Needs to know WHERE, WHAT and WHEN at a glance.
- Judges and team: a laptop dashboard shown live on a projector.

**Surface 1: Farmer field walk (mobile, Hindi)**
1. Welcome: "Ramesh-ji", "Khasra 124, Rampura", big play-audio button, one button "Shuru karein".
2. Map: satellite view of the field outline, the 10 m grid cell to visit glowing red, a GPS "you are here" dot, a distance chip "38 m aage", a direction arrow, and a vibrate + green check on arrival.
3. Photo steps with a camera frame overlay and an illustrated example: leaf top close-up, leaf underside (whiteflies), chewed leaves if any. Instant quality check: "Phir se lijiye" (blurry or dark) or a tick.
4. Walk around the patch: the GPS trail draws live as a red polygon, "0.44 acre".
5. Done: "Aapko 2 minute mein call aayega".

**Surface 2: Evidence card (farmer result screen and dashboard)**
- Cause in Hindi with the word "shak" (suspected): "Peela mosaic ka shak".
- Confidence ring 76% with band colour: High (75+) green, Medium amber, Low grey.
- One bar per signal with its share: Photo AI 19%, Traps 15%, Keypad answer 15%, Weather 7%, Advisory 7%, Crop stage, Satellite, Photo match.
- Zone thumbnail, "0.44 acre of 1.6 acre". Source line: "ICAR-NSRI salah, Kharif 2025".
- High: dose information plus a big "1: Drone Didi bulayein" button. Medium or Low: no spray button; "Drone Didi pehle jaanch karegi" or "Expert se baat".

**Surface 3: Drone Didi console (phone or tablet, Hindi + numbers)**
- Job queue cards sorted by urgency and distance: farmer, village, km, red or amber chip, "Aaj 6 se 9 baje".
- Job detail in three blocks:
  - WHERE: map with the field outline, the red spray zone only, a lawnmower flight path inside the zone, take-off point, "6 lines, 4 min".
  - WHAT: "Thiamethoxam 12.6% + Lambda-cyhalothrin 9.5% ZC", "20 ml in 4 L paani", a tank fill illustration, safety icons (gloves, mask, wind).
  - WHEN: 12-hour weather strip (rain, wind up to 10 km/h), recommended slot, battery count.
- Buttons: Accept / Decline, then Start mission (live drone dot on the path), then "Kaam poora" with a proof photo.
- Savings banner after the job: "1.2 acre bachaya, 60 ml dawa bachi".

**Surface 4: Live demo dashboard (laptop)**
Left: village map with field polygons coloured by risk and the flagged grid cells of the hero field. Right: a live event feed (call placed, key 1 pressed, SMS sent, photo received, evidence High 76%, Didi accepted, spraying, done). Top strip: farmer, crop, "40 din", today's band, a 15-day risk sparkline with "27 din pehle chetavani".

Deliver all 4 surfaces as connected, clickable screens with realistic Hindi copy and the numbers above.

## Part 2: Design rules (follow strictly)

**Direction**
- Purpose: a field tool used under sun and stress, not a marketing site. The first screen is the working screen; no hero sections.
- Tone: earthy, calm and trustworthy. Soil brown and soybean green neutrals, one alert red, amber, and a calm green for "safe". Never purple gradients, decorative blobs or stock photos of farmers.
- Memorable detail: the 10 m field grid. The sick cells glow, and the same grid appears on the farmer map, the evidence thumbnail, the Didi route and the dashboard.
- Flat backgrounds only, no gradients. No cards inside cards. Borders go all the way around a card or not at all.

**Type**
- Devanagari first: Mukta (or Noto Sans Devanagari) for Hindi; Manrope only for Latin numbers and labels. No italics, nothing heavier than bold.
- Use named text styles from one scale (12, 14, 16, 18, 20, 24, 30, 36, 48 px). Farmer screens: body at least 20 px, main action labels 24 px.
- `text-wrap: balance` on headings and `pretty` on body text, so no single word sits alone on a line. Tabular numbers for acres, ml, %, km, timers and counters.
- Sentence case. No hyphens in copy. Calm, specific messages, for example "Photo mil gayi" or "Photo dhundhli hai. Phir se lijiye." No exclamation marks.

**Spacing and shape**
- Spacing only in steps of 4, 8, 12, 16, 24, 32, 40, 48, 64 px.
- Nested corners: inner radius = outer radius minus the gap.
- Icons from Phosphor (or Solar), plus custom illustrations for the leaf, whitefly, caterpillar, drone and water tank. No Material icons.

**States (every screen)**
- Loading: skeletons shaped like the real layout, not spinners.
- Empty: "Aaj koi kaam nahi", with the next step.
- Error: what failed and what to do next, inline.
- Partial: for example, GPS weak, so show the last known point with a warning.
- Success: a confirmation plus the next action.
- Permission: camera or location denied, with a picture of how to allow it and a "Phir koshish karein" button.
- Hover, pressed (scale 0.98), visible focus ring, disabled.

**Accessibility (low literacy, outdoors)**
- Contrast at least 4.5:1, 7:1 on farmer screens. Never rely on colour alone: pair every red/amber/green with an icon and a word.
- Tap targets at least 56 px on farmer screens and 44 px elsewhere, with space between them.
- Every instruction has a play-audio button; audio plays once automatically on each new step.
- Every icon has a text label. Visible focus. Status changes are announced (live region).

**Motion**
- Only transform and opacity, 200 to 500 ms, ease-out curve `cubic-bezier(0.22,1,0.36,1)`. No `transition: all`.
- Motion only to show state: a cell pulsing at the target, the drone dot moving along the route, the confidence ring filling.
- With reduced motion, use a plain fade.

**Content realism**
- Use the real numbers above (76%, 0.44 acre, 27 days, 20 ml, 4 L). Invented people get specific regional names (Ramesh Patidar, Sunita Bai). Never invent statistics; leave `{{placeholder}}` where a fact is missing.
