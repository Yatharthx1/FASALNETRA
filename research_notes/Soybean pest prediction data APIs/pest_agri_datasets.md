# Indian and global pest-surveillance and agricultural datasets/APIs for soybean pest prediction in Malwa (MP)

Scope: data sources that could raise confidence of FasalNetra's soybean pest/disease forecasts for Mandsaur/Indore/Ujjain (whitefly+YMV, Spodoptera litura, semilooper, girdle beetle, Rhizoctonia aerial blight, rust, anthracnose). The app already uses GBIF. Research date: 1 Nov 2026. Session limited to about 15 tool calls, so many portals were checked only through secondary sources. Those cases are flagged.

## Q1. Which sources give field- or district-level, timely pest incidence data (ground truth) to calibrate or validate forecasts?

### Takeaway
No open, machine-readable, current pest-incidence feed for MP soybean was found. NPSS (2024, MoA&FW + NCIPM) and CROPSAP (Maharashtra, since 2009-10) collect field/village-level scout and farmer data. Neither has a documented public API, so access in practice means an MoU or a data request. The usable ground truth for a hackathon is (a) published, numeric weather-to-incidence rules from MP/Maharashtra studies, and (b) iNaturalist research-grade records, which help only for conspicuous taxa (S. litura yes, girdle beetle no).

### Cited Findings
**National Pest Surveillance System (NPSS)**
- NPSS is an AI-based pest monitoring system from MoA&FW, launched 15 Aug 2024 — [ClearIAS](https://www.clearias.com/?p=60878); [Morung Express](https://morungexpress.com/centre-to-launch-national-pest-surveillance-system-on-aug-15)
- It is implemented by the Directorate of Plant Protection, Quarantine & Storage (DPPQS) and ICAR-NCIPM. It runs as an Android app plus a web portal, identifies pests/diseases in 61 crops, gives management advisories for 15 major crops, and works in 6 languages — [Vikaspedia](https://agriculture.vikaspedia.in/viewcontent/agriculture/ict-applications-in-agriculture/national-pest-surveillance-system-ict-applications-in-agriculture-3?lgn=en)
- Farmers upload geotagged photos of infested fields, and the government stated this would show the location and extent of infestations — [Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fagriculture-ministry-launches-national-app-to-collect-info-on-pest-attacks-in-crops-3153384)
- Reported user numbers conflict: about 30,000 users (non-official site) — [C4S Courses](https://c4scourses.in/agriculture/artificial-intelligence-ai-driven-national-pest-surveillance-system-npss/). A target of about 14 crore farmers is also cited — [ClearIAS](https://www.clearias.com/?p=60878). No official usage statistics were found.
- No public API, open data download, or developer documentation for NPSS was found in any source reviewed.

**CROPSAP (Maharashtra Crop Pest Surveillance and Advisory Project)**
- Maharashtra's Department of Agriculture launched CROPSAP in 2009-10 under RKVY, after the 2008-09 soybean pest outbreak (mainly Spodoptera). It covers soybean, cotton, arhar, rice, gram and other crops. Pest scouts record incidence in fixed and random plots in representative villages on fixed days; data is analysed online and SMS advisories are issued — [StudyIQ](https://studyiq.com/articles/crop-pest-surveillance-system-and-advisory-project); [ICAR KRISHI PDF on ICT-based pest surveillance](https://krishi.icar.gov.in/jspui/bitstream/123456789/22404/1/Tbu_Crp_Information%20and%20Communication%20Technology%20based%20Pest%20Surveillance.pdf)
- NCIPM published the system design (web-based e-pest surveillance for soybean and cotton; field data captured by state plant-protection staff offline, then uploaded to a central database) in Singh et al. 2012, Indian J. Agric. Sci. 82(9), DOI 10.56093/ijas.v82i9.23835 — [ICAR ePubs](https://epubs.icar.org.in/index.php/IJAgS/article/view/23835)
- CROPSAP data has been used for a girdle beetle forewarning model. It combined daily village-level girdle beetle survey data with district daily weather for 20 Maharashtra districts, 2010–2015, and models explained roughly 74–95% of variation by zone — [GIS-based pest-weather model, J. Agrometeorology (typeset mirror)](https://typeset.io/pdf/gis-based-pest-weather-model-to-predict-the-incidence-of-3dzmhm919p.pdf)
- The KRISHI repository lists "Area wide e-pest surveillance for soybean in Maharashtra" (2014) with no attached dataset — [KRISHI record](https://krishi.icar.gov.in/jspui/handle/123456789/6637)

**ICAR-IISR (Indian Institute of Soybean Research, formerly NSRI/DSR), Indore**
- IISR issues bilingual weekly advisory PDFs, with an archive on the ICAR KRISHI repository (e.g., 7–13 Oct 2019 and 14–20 Oct 2019 issues) — [KRISHI PDF](https://krishi.icar.gov.in/jspui/bitstream/123456789/23316/1/WeeklyAdvisory%287%20to%2013%20Oct%202019%29.pdf); [KRISHI PDF](https://krishi.icar.gov.in/jspui/bitstream/123456789/23621/1/WeeklyAdvisory%20%2814%20to%2020%20Oct%202019%29.pdf)
- Advisories are also distributed via YouTube, Facebook, Twitter, and WhatsApp/Telegram groups for soy farmers — [Krishak Jagat PDF 2023](https://www.krishakjagat.org/wp-content/uploads/2023/06/Seed-Treatment.pdf)
- Example agronomic content: the 2024 kharif advice was to sow 2–3 varieties, 45 cm row spacing, seed rate 60–75 kg/ha — [Global Agriculture](https://www.global-agriculture.com/india-region/farmers-advised-to-sow-2-3-varieties-of-soybean-indian-institute-of-soybean-research/)

**iNaturalist (queried live, 1 Nov 2026)**
- Research-grade iNaturalist observations in India (place_id 6681) for girdle beetle *Obereopsis brevis*: **0 results** — [iNat API query](https://api.inaturalist.org/v1/observations?taxon_name=Obereopsis%20brevis&place_id=6681&quality_grade=research&per_page=1)
- Research-grade India counts by species within Spodoptera: *S. litura* 880, *S. mauritia* 46, *S. pecten* 30, *S. exigua* 21, *S. frugiperda* 11, plus others — [iNat species_counts query](https://api.inaturalist.org/v1/observations/species_counts?place_id=6681&quality_grade=research&taxon_id=47157&q=Spodoptera)

### Inferences
- Ground truth realistically available in a day: iNaturalist (open reads, no key), published MP threshold rules (Q3), and IISR advisory text (scrape or parse PDFs as "expert label" weeks, e.g., when IISR warns of girdle beetle or YMV, use that as a weak positive label for Malwa).
- iNaturalist research-grade data is largely already in GBIF, because iNat exports research-grade CC-licensed records to GBIF. The additive value is mainly (a) "needs ID" / casual records, which GBIF lacks, and (b) fresher data via the live API. It does not fix the girdle beetle gap: the beetle is small, damage is internal, and it is rarely photographed. The iNat-to-GBIF relationship is general knowledge and was not re-verified this session.
- Records are presence-only and biased toward urban areas and photographers. Treat them as a "pest present in region this season" prior, not as incidence.
- NPSS is the most promising future ground truth: field-level, geotagged, multi-crop including soybean, and national. Access would need a request to DPPQS/NCIPM (likely an MoU or a data-sharing request under NDSAP). It is not feasible within a hackathon day.
- CROPSAP is the best historical soybean incidence dataset (village-level, daily/weekly, 2009–present) but covers Maharashtra, not MP. Vidarbha/Marathwada climate is reasonably close to Malwa, so it could validate model shape if obtained via NCIPM or Maharashtra DoA.

### Gaps
- NCIPM's legacy e-pest surveillance portal (ncipm.org.in / e-Pest Surveillance and Advisory): current URL, live status, and whether it has public dashboards could not be verified this session. Status unknown; it may have been superseded by NPSS.
- NPSS portal URL and any public dashboard or district aggregates were not found. No evidence of an API.
- MP State Agriculture Department (Kisan Kalyan tatha Krishi Vikas) pest bulletins: no machine-readable source found. Not researched in depth due to the call budget.
- No 2025–2026 IISR advisories surfaced in search. It is unclear whether there is an RSS feed or structured page (the IISR site is iisrindore.icar.gov.in, but this was not verified this session).
- iNat counts for *Bemisia tabaci*, semilooper (*Chrysodeixis acuta*/*Gesonia gemma*), and soybean rust/anthracnose fungi in India were not queried.

## Q2. Access method, cost, limits, granularity, update frequency and reliability of each source; which can a team get within a day vs needing an MoU?

### Takeaway
Same-day access: iNaturalist (open), EPPO (free registration plus token), data.gov.in OGD/Agmarknet (free key, flaky), ICRISAT DLD (open download, ends 2017), data.gov.in MP district soybean area (open), and SoilGrids (open; not verified this session). MoU or request needed: NPSS, CROPSAP raw data, SHC bulk data at scale, Krishi-DSS/AgriStack. UPAg and Krishi-DSS have no documented public API.

### Cited Findings
**Market — Agmarknet via data.gov.in**
- The data.gov.in resource "Current Daily Price of Various Commodities from Various Markets (Mandi)" provides daily min, max and modal wholesale prices sourced from Agmarknet — [data.gov.in](https://data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi)
- It requires a free data.gov.in account and API key. No official rate limit was found. Third-party tools note that the shared sample key is rate-limited — [Apify scraper page](https://apify.com/themineworks/india-data-gov-scraper)
- Reliability: one developer README says data.gov.in is "frequently down / WAF-blocked" — [Agmarknet MCP server](https://glama.ai/mcp/servers/Krishna-Baldwa/agmarket-mcp)
- Alternative: Ashoka University's CEDA Agmarknet API (key required) has historical prices back to 2000 — [CEDA README](https://agmarknet.ceda.ashoka.edu.in/README.html)

**Soil — Soil Health Card (SHC)**
- No documented public SHC API was found. The revamped portal has national, state and district dashboards — [Rajya Sabha reply, Aug 2024](https://rsdebate.nic.in/bitstream/123456789/750994/1/PQ_265_09082024_U2098_p118_p119.pdf)
- The India Data Portal mirror "Soil Nutrient Analysis" is village-level and yearly, last updated 26 Aug 2025, and covers 738 districts — [India Data Portal (CKAN)](https://ckandev.indiadataportal.com/dataset/soil-health-card/resource/024cf507-4281-4c89-a40e-37b5add3a4df)
- AIKosh (IndiaAI) lists a nationwide SHC dataset from about 5 crore samples — [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/shc_dataset.html)

**Crop statistics**
- UPAg (upag.gov.in, launched Sep 2023) covers area, production, yield, crop profiles, GVA and market intelligence, triangulated from state data, MNCFC and other sources — [Vikaspedia](https://en.vikaspedia.in/agriculture/agri-directory/unified-portal-for-agricultural-statistics). A third-party API marketplace states that UPAg has **no documented public API**, and its own JSON wrapper offers no district-level endpoint — [Parse.bot listing](https://parse.bot/marketplace/07fa78ed-8d38-4eeb-a4dd-9f3482166be4/upag-gov-in-api)
- ICRISAT District Level Database (DLD): 1966–2017, 592 districts in 20 states, apportioned to 1966/1991/2001 boundaries, hosted on ICRISAT Dataverse (DOI 10.21421/D2/XFB1BZ) with a dashboard at data.icrisat.org/dld — [ICAR KRISHI record](https://krishi.icar.gov.in/ohs-2.3.1/index.php/record/view/662239)
- data.gov.in has the catalogue "District wise Soyabean Farming Area in Madhya Pradesh" (NDSAP) — [data.gov.in catalog](https://www.data.gov.in/catalog/district-wise-soyabean-farming-area-madhya-pradesh)

**Krishi-DSS / Digital Agriculture Mission**
- Krishi-DSS was launched 16 Aug 2024. It is a geospatial platform built on ISRO's VEDAS and RISAT-1A data, with modules for a soil information system, a ground-truth data library for researchers and industry, drought (NADAMS), rice-fallow mapping, and crop insurance — [Business Standard](https://business-standard.com/amp/india-news/govt-launches-satellite-based-agricultural-decision-support-system-124081600826_1.html); [IASGyan](https://iasgyan.in/daily-current-affairs/krishi-decision-support-system-krishi-dss); [Krishi Jagran](https://krishijagran.com/news/krishi-dss-satellite-based-farm-decision-support-system-launched)
- No public API documentation for Krishi-DSS was found in these sources.

**EPPO Global Database**
- REST API access is free under an Open Data Licence after registering at data.eppo.int. The token is used via the R package `pestr` (`create_eppo_token()`, `check_eppo_token()`) — [CRAN pestr manual](https://stat.ethz.ch/CRAN/web/packages/pestr/refman/pestr.html); [EPPO](https://eppo.int/DATABASES/pqr/pqr.htm)

### Inferences
**Feasibility matrix** (based on the findings above; items marked "unverified" are background knowledge):

| Source | Adds to FasalNetra | Access | Cost | Granularity | Update | Within a day? |
|---|---|---|---|---|---|---|
| iNaturalist API | Presence/phenology for S. litura, possibly whitefly; not girdle beetle | Open reads, no key (published rate guidance about 1 req/s, unverified) | Free | Point (obscured for some) | Live | Yes |
| NPSS | Field-level geotagged incidence (ideal ground truth) | Request to DPPQS/NCIPM, likely MoU | Free (govt) | Field | Near-real-time | No |
| CROPSAP | Village-level soybean incidence 2009–present (Maharashtra) | Request to Maharashtra DoA / NCIPM | — | Village | Weekly | No |
| IISR Indore advisories | Expert weekly pest-alert labels for MP | Public PDFs/social media; scrape | Free | State/region | Weekly in kharif | Yes (manual) |
| Agmarknet (data.gov.in) | Price → economic threshold / spray-or-not | Free API key, instant signup | Free | Mandi (Indore, Ujjain, Mandsaur mandis) | Daily | Yes, but flaky |
| SHC | Soil N/P/K/OC/pH → crop vigour / Rhizoctonia risk context | Dashboards; bulk via mirrors | Free | Village | Yearly | Partly (mirror CSV) |
| SoilGrids (ISRIC) | 250 m soil properties (texture, pH, SOC) | Open REST (unverified) | Free | 250 m grid | Static | Yes |
| ICRISAT DLD | Historical district soybean area 1966–2017 | Open download | Free | District | Ends 2017 | Yes |
| data.gov.in MP soybean area | District soybean area for MP | Open download | Free | District | Irregular | Yes |
| UPAg | Current crop area/production | Web UI; no public API | Free | State, maybe district | Seasonal | Scrape only |
| Krishi-DSS / AgriStack | Crop maps, ground-truth library, farm IDs | Govt login / MoU | — | Field/plot | Varies | No |
| EPPO API | Host range, distribution, taxonomy codes | Free registration + token | Free | Country | Ongoing | Yes |
| CABI CPC / Digital Library | Biology, thresholds, distribution maps | Subscription (CABI CPC became open access in 2022, unverified) | Mostly free web; no open API | Country/state | Ongoing | Read-only |

- For spread risk, district soybean area is very relevant. Mandsaur, Ujjain and Indore are among MP's major soybean districts, so high contiguous soybean area raises neighbour-field spread risk for whitefly/YMV and Spodoptera. DLD plus data.gov.in suffice for a static "host density" weight.
- Agmarknet adds economic-threshold logic: spray recommendation = pest density above ETL and expected loss × price > spray cost. Soybean modal prices at Indore mandi make the advice concrete.

### Gaps
- Bhuvan crop maps: whether ISRO Bhuvan/VEDAS exposes a district soybean-area or kharif crop-map WMS was not checked this session.
- AgriStack (farmer registry, crop sown registry via Digital Crop Survey) API terms were not researched. They are likely restricted to government-approved entities, which is not confirmed.
- SoilGrids endpoint, limits, and current status (ISRIC has had service interruptions/beta REST) were not verified this session.
- CABI Compendium licensing/API status was not verified this session.
- No official data.gov.in rate limit was found. Whether the Agmarknet resource API is currently active needs checking (the snapshot said "API does not exist" for one resource).
- DES district-wise APY (aps.dac.gov.in / data.desagri.gov.in) was not checked.

## Q3. Published soybean pest forecasting models for India with numeric thresholds or degree-days (for rule calibration)

### Takeaway
MP-specific, numeric rules exist for YMV, and thermal constants exist for S. litura on soybean. These are the most valuable "calibration" assets: they are directly codeable today. Girdle beetle drivers (RH, temperature) are documented, mostly as correlations rather than cut-offs. Rust and anthracnose thresholds were not retrieved.

### Cited Findings
**YMV / whitefly (MP)**
- Srivastava et al. 2021 (JNKVV; IJBB 58(5):486-497) studied Tikamgarh, Chhatarpur, Datia and Jabalpur in kharif 2015–2019. Peak YMD is predicted when, over the previous 2 weeks: **whitefly > 12/plant AND Tmax > 33°C AND passive (break) monsoon phase > 1 week**. Transmission is higher when a dry spell coincides with **Tmax > 33°C for ≥ 5 days**. Tmax, sunshine hours and whitefly are positively related to YMD; rainfall and evening RH are negatively related — [NISCPR IJBB](https://or.niscpr.res.in/index.php/IJBB/article/view/2875); [KRISHI record](https://krishi.icar.gov.in/ohs-2.3.1/index.php/record/view/668843)
- In central India, YMD severity correlated with whitefly population (r = 0.91) and mean temperature (r = 0.77) — [Australasian Plant Pathology 2023, 52:165-179 (pestinfo summary)](https://wiki.pestinfo.org/wiki/Australasian_Plant_Pathology_(2023)_52,_165-179)
- Jabalpur kharif 2021 study relating whiteflies, YMD severity, weather and crop age — [Legume Research 2025, DOI 10.18805/IJARe.A-6252](https://arccjournals.com/journal/legume-research-an-international-journal/a-6252)
- Uttarakhand Tarai (Pantnagar, 2001–2020): an ANN with weather indices was best for YMV forewarning (calibration nRMSE 3.08%). This is not MP — [J. Reliability & Statistical Studies](https://journals.riverpublishers.com/index.php/JRSS/article/view/28587)

**Spodoptera litura (soybean-specific thermal constants)**
- Prasad et al. 2021, J. Agrometeorology 23(2), DOI 10.54386/jam.v23i2.63. Lower developmental thresholds on soybean: egg about 11.3°C, larva 11.7°C, pupa 11.5°C, total immature **about 12.1°C** (Campbell linear model; fitted in the 20–35°C linear range). **489 degree-days per generation (larva to larva)** was used to validate phenology against field surveillance data — [ICAR KRISHI PDF](https://krishi.icar.gov.in/jspui/bitstream/123456789/73997/1/JAM_spodoptera%20litura.pdf); [ICAR ePubs IJPP (temp-dependent biology on soybean)](https://epubs.icar.org.in/index.php/IJPP/article/view/105777)
- Older values (Rao et al. 1989): egg about 64 DD above 8°C; larva 303 DD and pupa 155 DD above 10°C — [USDA CPHST datasheet 2014](https://caps.ceris.purdue.edu/wp-content/uploads/2025/07/Spodoptera-litura_CPHST-Datasheet_2014.pdf)

**Girdle beetle (Obereopsis brevis)**
- An IISR Indore CROPSAP-based model found infestation significantly positively correlated with RH of the current and preceding weeks. It used Tmax, Tmin, RH and rainfall with lags — [typeset mirror of J. Agromet paper](https://typeset.io/pdf/gis-based-pest-weather-model-to-predict-the-incidence-of-3dzmhm919p.pdf)
- A krishikosh thesis reports incidence positively correlated with Tmax (r = 0.751*) and Tmin (r = 0.721**); study location unclear — [Krishikosh](https://krishikosh.egranth.ac.in/handle/1/5810169395)
- Raipur (Chhattisgarh) kharif 2012: peak activity at Tmax 31.9°C, Tmin 23.9°C, morning RH 91%, evening RH 56%, rainfall 9.2 mm/week — [Indian J. Entomology](https://indianentomology.org/index.php/ije/article/download/968/1043/5921)
- Sehore (MP) kharif 2015 weekly incidence tables — [J. Pharmacognosy & Phytochemistry 2019](https://www.phytojournal.com/archives/2019/vol8issue4/PartAW/8-4-590-649.pdf)

### Inferences
- Codeable rules:
  - YMV risk is HIGH if (2-week Tmax > 33°C) and (monsoon break ≥ 7 days, e.g., < 2.5 mm/day) and (whitefly > 12/plant, or a proxy when counts are unavailable).
  - S. litura generation timing: accumulate DD = max(0, Tmean − 12.1) from first moth catch or sowing; flag a new larval generation every ~489 DD.
  - Girdle beetle risk rises with high RH (morning ≥ 90%) and Tmax about 30–32°C after about 30–45 DAS.
- Thresholds are from Bundelkhand/Jabalpur (YMV) and Maharashtra (girdle beetle). Malwa transfer is plausible but unvalidated, so label confidence accordingly.

### Gaps
- Soybean rust and anthracnose/aerial blight (Rhizoctonia) numeric thresholds: the rust query failed (tool error) and the others were not searched. Not retrieved.
- Semilooper (Chrysodeixis/Gesonia) degree-day or weather thresholds: not searched.
- Economic threshold levels (ETLs) per pest from IISR package of practices: not retrieved this session.
- Full text of the girdle beetle CROPSAP model (coefficients, zone equations) was not retrieved, only the abstract.
