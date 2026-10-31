# Kindwise disease-diagnosis APIs (crop.health vs plant.id / plant.health) for soybean in Madhya Pradesh

Research date: 2026-11-01. Kindwise pages carry few dates. Each finding is flagged with whatever date I could see.

## 1. Does crop.health support soybean, and which soybean pests and diseases does it cover?

### Takeaway
crop.health officially supports soybean (*Glycine max*) as one of 23 crops, with about 288 disease and pest classes across all crops. Kindwise does not publish a per-crop class list, so I could not confirm any specific soybean class (MYMIV, girdle beetle, *Phakopsora*, and so on). The demo output shows that many pest classes are at family level (Aleyrodidae, Noctuidae, Erebidae, Geometridae), not species level.

### Cited Findings
- crop.health lists 23 crops, and Soybean (*Glycine max*) is one of them. The full list is Apple, Banana, Barley, Cassava, Citrus, Cocoa, Coffee, Corn, Cotton, Cucumber, Eggplant, Garlic, Grapevine, Oil palm, Onion, Potato, Rice, Soybean, Sugarcane, Tea, Tobacco, Tomato and Wheat — [Kindwise blog, 26 Mar 2024](https://www.kindwise.com/post/crop-health-curing-crops-empowering-farmers); [crop.health product page](https://www.kindwise.com/crop-health)
- The product page gives about 288 classes: roughly 180 pests, 80 fungal, 20 viral, 20 bacterial and 2 other. The FAQ says "nearly 288 classes" — [kindwise.com/crop-health](https://www.kindwise.com/crop-health)
- Kindwise says diseases were "carefully selected based on their occurrence in each of the crops", with a focus on pests and infectious diseases. The disease information is aligned with the EPPO database — [Kindwise blog 2024](https://www.kindwise.com/post/crop-health-curing-crops-empowering-farmers); [search summary of crop.health page](https://www.kindwise.com/crop-health)
- The blog names example classes (Colorado potato beetle, aphids, grasshoppers, bacterial spot, fire blight, early blight, powdery mildew, Potato Virus Y, Banana bunchy top virus) and mentions "nutrient deficiencies". It names no soybean-specific classes — [Kindwise blog 2024](https://www.kindwise.com/post/crop-health-curing-crops-empowering-farmers)
- The public demo collection contains no soybean images. Its outputs still show the class granularity:
  - Whitefly is returned as **Aleyrodidae** (family level).
  - Caterpillars are returned as families such as **Noctuidae**, **Erebidae** and **Geometridae** (the closest match to a "looper").
  - **Rhizoctonia solani** exists as a class.
  - Rusts appear as *Puccinia polysora* on maize.
  - Anthracnose appears as **Colletotrichum**.
  - Nutrient deficiency is a class.
  - Viruses seen include Tomato yellow leaf curl virus and Tomato spotted wilt virus. No "mosaic virus" class appeared, and no Spodoptera, girdle beetle, frogeye or bacterial pustule class appeared.
  - Source: [crop.health demo collection](https://crop.kindwise.com/collection/x8X1VTfxUshyS7z)
- The GitHub examples README has no class or crop list. It points only to the docs — [flowerchecker/crop-health-examples](https://github.com/flowerchecker/crop-health-examples)
- crop-disease-api.org did not resolve (DNS ENOTFOUND) when I tried it on 2026-11-01, so I could not check its entity pages — (attempted fetch of https://crop-disease-api.org/)

### Inferences
- **Spodoptera litura and semilooper (Chrysodeixis):** the API will probably return them as family-level Noctuidae (Spodoptera, and some loopers) or Erebidae/Noctuidae. That is useful for "caterpillar defoliator, spray advice", but it will not name the species.
- **Whitefly:** likely to be detected as Aleyrodidae.
- **Rhizoctonia aerial blight:** probably covered through the *Rhizoctonia solani* class.
- **Anthracnose:** probably covered through *Colletotrichum*.
- **Nutrient deficiency:** a generic class exists.
- **Soybean rust (*Phakopsora pachyrhizi*), frogeye (*Cercospora sojina*), bacterial pustule (*Xanthomonas*) and charcoal rot (*Macrophomina*):** these are plausible for a soybean crop entry, but I could not verify them.
- **MYMIV / yellow mosaic:** this is the biggest risk. Viral classes are only about 20 across 23 crops, and no begomovirus of legumes appeared in any source.
- **Girdle beetle (*Obereopsis brevis*):** very unlikely to be a class. It is India-specific, and its damage (girdles on the stem, then wilting) is hard to diagnose from a photo.
- **Practical step:** run a probe with 5–10 field photos of each target problem using the 100 free credits (section 3). The `id` and `scientific_name` in the responses will show which classes exist. Alternatively, email support@kindwise.com and ask for the soybean class list.

### Gaps
- I found no public per-crop class list for soybean. The docs at crop.kindwise.com/docs redirect to a Postman page that did not render for the fetcher.
- I could not check the crop-disease-api.org entity pages because the domain was unreachable.

## 2. How does plant.id health assessment (plant.health) differ, and does it cover soybean field pests?

### Takeaway
plant.health is the general-purpose model, trained mostly on houseplant and ornamental annotations. It has 548 classes (up from 90), a top-1 of 58% and a top-3 of 73%. crop.health is the food-crop sibling and is the right product for soybean fields. The two products use different hosts and endpoints.

### Cited Findings
- plant.health has 548 classes covering abiotic disorders, pests, diseases and harmless look-alikes. Kindwise says "most annotations are for houseplants and ornamentals" and positions crop.health as the food-crop product — [kindwise.com/plant-health](https://www.kindwise.com/plant-health)
- Kindwise reports these accuracy figures for the expanded model on images of sick plants:
  - Top-1: 58%
  - Top-3: 73%
  - Overall accuracy is described as comparable to the prior model.
  - The post is undated.
  - Source: [Kindwise blog: Plant.health major expansion](https://www.kindwise.com/post/plant-health-major-expansion-from-90-to-500-diseases)
- The 2022 Health Assessment release (20 Apr 2022) had 90 classes chosen for "the plant health issues of the end-users" (mechanical damage, mites, fungus gnats, springtails). Its top-3 accuracy was 61.2% — [Kindwise blog 2022, older](https://www.kindwise.com/post/health-assessment-production-release)
- Credit costs on plant.health:
  - A diagnosis costs 1 credit.
  - `health=auto` costs 2 credits when it returns a full health result.
  - `health=all` (identification plus health) costs 2 credits.
  - The `disease_level=general` parameter limits output to general classes.
  - Source: [kindwise.com/plant-health](https://www.kindwise.com/plant-health)
- The endpoint is described as a separate `/health_assessment` endpoint that works independently of species identification — [Kindwise blog 2022](https://www.kindwise.com/post/health-assessment-production-release)

### Inferences
- plant.health does not identify the crop, and its classes are not tuned to soybean field pests. Use crop.health for FasalNetra.
- Do not combine the two products. A key is tied to a product (section 4), so calling both would double the cost for little gain.

### Gaps
- I did not confirm the exact plant.id v3 health URL from a fetched source. From memory of the docs it is `https://plant.id/api/v3/health_assessment`; verify it before use.
- I found no class list for plant.health beyond the 21 classes in the website library.

## 3. Pricing: free credits, cost per call, plans, non-profit programmes

### Takeaway
Pricing is shared across Kindwise products. New sign-ups get 100 free credits, and one crop.health identification costs 1 credit. After that, prepaid credits cost €0.05 per call (€50 for 1,000 calls), falling to €0.01 per call at 1.5 million calls. There is a non-profit programme for environmental NGOs. I found no academic or hackathon programme.

### Cited Findings
- The free trial gives 100 credits after registration, and one identification costs one credit — [kindwise.com/pricing](https://www.kindwise.com/pricing) (fetched 2026-11-01, current)
- Prepaid tiers:

  | Tier | Credits | Price per call | Minimum order |
  |---|---|---|---|
  | A | 1,000+ | €0.05 | €50 |
  | B | 10,000+ | €0.03 | €300 |
  | C | 50,000+ | €0.02 | €1,000 |
  | D | 200,000+ | €0.015 | €3,000 |
  | E | 800,000+ | €0.012 | €9,600 |
  | F | 1.5M+ | €0.01 | €15,000 |

  Source: [kindwise.com/pricing](https://www.kindwise.com/pricing)
- Credits are valid for 3 months. The page says this "doesn't apply to purchases under 30,000 credits"; the wording is ambiguous — [kindwise.com/pricing](https://www.kindwise.com/pricing)
- Credits are bought through the admin panel (Business plan). A Custom plan covers bespoke models. Discounts are available for identifying fewer classes; contact support@kindwise.com — [kindwise.com/pricing](https://www.kindwise.com/pricing)
- NGOs with a reliable track record and an environmental focus can get special pricing — [kindwise.com/pricing](https://www.kindwise.com/pricing)

### Inferences
- **Cost per 1,000 calls:** about €50 (roughly ₹4,600–5,000) at tier A, and €30 at tier B.
- **Demo budget:** 100 free credits are enough for class probing plus a live demo, but not for a field pilot.
- **Ask Kindwise:** a short email to support@kindwise.com asking for hackathon credits is worth sending, but no programme is advertised.

### Gaps
- I found no published academic, student or hackathon programme.

## 4. Sign-up, key process, and limits

### Takeaway
Sign-up is self-serve through the Kindwise admin panel. The GitHub README links admin.mlapi.ai/signup, which is the older domain. The current panel is admin.kindwise.com. You choose the product when creating the key, so request a crop.health key specifically.

### Cited Findings
- The README says to sign up at https://admin.mlapi.ai/signup. The README also warns that crop.health is in beta and may change incompatibly — [crop-health-examples README](https://github.com/flowerchecker/crop-health-examples)
- `GET /api/v1/usage_info` returns the key's status, limits and remaining credits — [crop.health OpenAPI](https://crop.kindwise.com/api/v1/openapi.yaml)
- The product page offers "Try demo" and an API-key sign-up — [kindwise.com/crop-health](https://www.kindwise.com/crop-health)

### Inferences
- The redirect from crop.kindwise.com/docs to Postman and the "admin.mlapi.ai" link suggest that admin.kindwise.com is the current panel (mlapi.ai is the legacy brand).
- Keys appear to be per product: crop.health uses crop.kindwise.com and plant.id uses plant.id. Each has its own usage endpoint, so a plant.id key should not be expected to work on crop.kindwise.com.
- Self-serve sign-up is likely instant, but I could not verify this.

### Gaps
- Approval time, published rate limits (requests per second) and whether trial keys have daily caps are not documented in the sources I fetched. Check `usage_info` after sign-up.

## 5. API details: endpoints, auth, request and response fields, location/date, languages, latency

### Takeaway
Send a POST to `https://crop.kindwise.com/api/v1/identification` with the key in the `Api-Key` header and a JSON body of base64 `images` plus optional `latitude`, `longitude`, `datetime` and `similar_images`. Pass `details` and `language` as query parameters. Read `result.crop.suggestions[]` and `result.disease.suggestions[]`, each with `probability`. Kindwise says location and date can improve accuracy.

### Cited Findings
- **Endpoints:**
  - `POST /api/v1/identification`
  - `GET /api/v1/identification/{access_token}` (retrieve results, including async results, or re-fetch in another language or with other details)
  - `DELETE /api/v1/identification/{access_token}`
  - `GET /api/v1/usage_info`
  - `POST /api/v1/identification/{access_token}/feedback`
  - Source: [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **Auth:** the `Api-Key` header — [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **Request body fields** (sent as JSON or multipart):
  - `images`: a list of base64 strings. Required.
  - `latitude`, `longitude`: optional. The spec says they can improve accuracy.
  - `datetime`: optional ISO date, for example `2023-06-22`, which helps with seasonal differences.
  - `similar_images`: optional boolean.
  - `custom_id`: optional integer.
  - Source: [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **Query parameters:**
  - `details`: comma-separated list.
  - `language`: up to 3 ISO 639-1 codes, default `en`.
  - `async=true`: returns before identification finishes; poll with GET.
  - Source: [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **Response fields:**
  - Top level: `access_token`, `status`, `created`, `completed`, `input`, `model_version`.
  - `result.is_plant` contains `binary`, `probability` and `threshold`.
  - `result.crop.suggestions[]` and `result.disease.suggestions[]` hold the predictions.
  - Each suggestion has `id`, `name`, `scientific_name`, `probability`, `similar_images` and `details`.
  - `id` is stable, while `name` may change.
  - Source: [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **`details` options for diseases:** `type`, `common_names`, `taxonomy`, `eppo_code`, `eppo_regulation_status`, `gbif_id`, `image`, `images`, `wiki_url`, `wiki_description`, `description`, `treatment`, `symptoms`, `severity`, `spreading`. For crops: `gbif_id`, `image`, `images`. Some details are licensed and must be attributed — [OpenAPI spec](https://crop.kindwise.com/api/v1/openapi.yaml)
- **Python client:** `pip install kindwise-api-client` gives `CropHealthApi(key).identify(path, details=[...])` — [crop-health-examples](https://github.com/flowerchecker/crop-health-examples)
- **Localization:** common names, wiki descriptions and URLs can be requested per language. The product page has a top-15-languages coverage chart, but its values were not readable as text — [kindwise.com/crop-health](https://www.kindwise.com/crop-health)

### Inferences
- Pin on the stable suggestion `id` (not `name`) in FasalNetra's mapping table from a class to ICAR/IISR advisories.
- Hindi (`hi`) is a valid ISO code, but its coverage is unverified. The app should probably translate itself, using its own Hindi advisory text keyed by class `id`, and keep `en` as a fallback.
- Always send MP latitude/longitude and the capture date, because kharif seasonality is exactly what the `datetime` hint targets.

### Gaps
- Whether Hindi is among the 15 covered languages is unconfirmed.
- No latency figures are published. Measure them during the trial.

## 6. Published accuracy and independent evaluations

### Takeaway
Kindwise reports crop.health accuracy of 85% top-1 and 93% top-3 on its own validation set, but only 48% top-1 and 66% top-3 on an independent set of Twitter images. That gap is the realistic expectation for farmer phone photos. I found nothing specific to soybean or India.

### Cited Findings
- crop.health scores 85% top-1 and 93% top-3 on validation, and 48% top-1 and 66% top-3 on the Twitter-sourced set — [Kindwise blog, Mar 2024](https://www.kindwise.com/post/crop-health-curing-crops-empowering-farmers); [crop.health page](https://www.kindwise.com/crop-health)
- plant.health scores 58% top-1 and 73% top-3 on sick-plant images (vendor figure) — [Kindwise blog](https://www.kindwise.com/post/plant-health-major-expansion-from-90-to-500-diseases)

### Inferences
- Treat crop.health output as a top-3 shortlist and have the farmer confirm it with symptom questions or images. Do not treat it as a final diagnosis.

### Gaps
- I found no independent or peer-reviewed evaluation of crop.health on soybean or on Indian crops.

## 7. Alternatives (only those with obtainable API access)

### Takeaway
Plantix (PEAT) has a Vision API covering 57 crops, with Indian agribusiness partners. Access is sales-led (book a demo), not a self-serve key. I found no public evidence of a self-serve Agrio API. Kindwise is the most hackathon-friendly option.

### Cited Findings
- The Plantix Crop Health or Vision API covers:
  - 57 crops
  - 970 catalogued stressors and "800+ diagnoses combinations"
  - 19 languages
  - Indian partners: ITC MAARS (9 states), DeHaat, AgroStar, Coromandel
  - Access is through "Book a demo", with docs at b2b.plantix.net.
  - No pricing is shown.
  - Source: [plantix.net Vision API](https://plantix.net/en/business/plantix-vision-api)
- An older or regional Plantix page states more than 30 crops and more than 780 diseases, which conflicts with the 57-crop figure — [plantix.net search results](https://plantix.net/en/business/plantix-vision-api)

### Inferences
- Plantix probably covers soybean and Indian pests better, given its India-first data, but it cannot be obtained quickly enough for a hackathon.
- A self-hosted model trained on Indian soybean datasets is the fallback for MYMIV and girdle beetle if the Kindwise probe shows those classes are missing.

### Gaps
- I did not verify Agrio API availability; no search results came back.
- I did not evaluate PlantVillage-based models (PlantVillage has no soybean disease classes beyond "healthy", which is from memory and unverified here).
