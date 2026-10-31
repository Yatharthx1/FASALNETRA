# Weather, soil-moisture and satellite data APIs for soybean pest and disease risk in Malwa, MP (additive to Open-Meteo, Sentinel-2 L2A on Planetary Computer, and SRTM)

Research date: 1 Nov 2026. Baseline already in the app: Open-Meteo hourly forecast (16 days) plus archive; Sentinel-2 L2A NDVI, NDRE and NDMI via Microsoft Planetary Computer (MPC); SRTM terrain.

## Q1. Which sources meaningfully improve pest/disease prediction beyond Open-Meteo + Sentinel-2?

### Takeaway
There are four additions worth making, and the cheapest is inside the API the app already calls. First, request Open-Meteo's own soil moisture, soil temperature, ET0/actual ET, VPD and the daily leaf-wetness probability, plus its ERA5-Land and ensemble archives. Second, add Sentinel-1 SAR from the same MPC STAC endpoint, because optical imagery is often cloud-blocked during the monsoon. Third, add an independent observed-rainfall product (IMERG Early at about 4 h latency, CHIRPS, or IMD 0.25° gridded) to correct model rainfall. Fourth, add SMAP L4 root-zone soil moisture for waterlogging and drought context. IMD, MOSDAC, Bhuvan and VEDAS are valuable for official advisories and validation. They are poor as same-day hackathon APIs. Planet NICFI is effectively gone.

### Cited Findings

**Disease and weather links (why moisture and humidity variables matter)**
- Central India, 2017–2019: the conditions most favourable to rapid progress of Rhizoctonia aerial blight were a weekly mean Tmax of 27–30°C and mean RH of 80–90% in the current week, plus more rainfall and rainy days in the previous week. Lagged rainfall and RH therefore matter, and observed rainfall improves this feature. — [IJBSM/pphouse article](https://ojs.pphouse.org/index.php/IJBSM/article/view/6028); [J. Agrometeorology 10.54386/jam.v23i1.90](https://zendy.io/title/10.54386/jam.v23i1.90)
- A central India modelling study: aerial blight was favoured by dense canopy, 28–30°C, RH >85% and well-distributed rainfall. Canopy density can be proxied by NDVI from Sentinel-2, or by Sentinel-1 VH backscatter when skies are cloudy. — [Crop-weather severity prediction of aerial blight (DOAJ record)](https://openaccess.library.uitm.edu.my/find/Record/doaj-art-4e56c4251105426fa55fa070a38934d5)
- Uttarakhand and Assam studies found severity positively correlated with evening/morning RH and rainfall, and negatively with Tmin. The direction of the temperature effects varies by region. — [Krishikosh thesis](https://krishikosh.egranth.ac.in/items/95d236ab-e02e-49e6-9e6c-d2e252d051b8/full); [Legume Research LR-5538](https://arccjournals.com/journal/legume-research-an-international-journal/LR-5538)

**Open-Meteo extras (no new key; already integrated)**
- Forecast API hourly soil temperature at 0, 6, 18 and 54 cm, and soil moisture at 0–1, 1–3, 3–9, 9–27 and 27–81 cm (m³/m³). Also `evapotranspiration` (actual, accounting for soil water), `et0_fao_evapotranspiration` (FAO-56 Penman-Monteith, hourly and daily) and `vapour_pressure_deficit` (kPa). The docs note that transpiration rises above 1.6 kPa and falls below 0.4 kPa. — [Open-Meteo forecast docs](https://open-meteo.com/en/docs)
- Leaf wetness: only a **daily "Mean Leaf Wetness Probability"** aggregate is listed. There is no hourly leaf-wetness variable, so hourly leaf-wetness duration has to be built from RH ≥ ~90%, dew point depression, and precipitation. — [Open-Meteo forecast docs](https://open-meteo.com/en/docs)
- Historical API models:

  | Model | Resolution | Start | Update / latency |
  |---|---|---|---|
  | ERA5 | 0.25° | 1940 | Daily, about 5 days behind |
  | ERA5-Land | 0.1° | 1950 | Daily, about 5 days behind |
  | ECMWF IFS | 9 km | 2017 | Every 6 h, no delay |

  Soil temperature and moisture are available at 0–7, 7–28, 28–100 and 100–255 cm. — [Open-Meteo historical API docs](https://open-meteo.com/en/docs/historical-weather-api)
- Ensemble API models include ECMWF IFS 0.25° (51 members, 15 days), ECMWF AIFS (51), NOAA GFS ensemble 0.25° (31 members, 10 days; 0.5° to 35 days), ICON-EPS global (40 members, ~13 km, 7.5 days), CMC GEM (21), BOM ACCESS-GE (18) and Google WeatherNext 2 (64 members, 0.25°, 15 days). Soil moisture and ET0 are available in the ensembles; leaf wetness is not. Ensembles allow a probability of exceedance, for example "P(RH>85% for 3+ days)", instead of one deterministic run. — [Open-Meteo ensemble API docs](https://open-meteo.com/en/docs/ensemble-api)
- ERA5-Land is a land-surface replay forced by ERA5. It does not assimilate soil-moisture observations directly. — [ECMWF Confluence via search](https://confluence.ecmwf.int/x/CygiEw)

**Sentinel-1 SAR (C-band; cloud-penetrating)**
- MPC data is anonymously accessible. STAC metadata needs no account, and a SAS token for blob assets can be requested without registering, per collection. This is the same mechanism the app already uses for Sentinel-2. — [MPC SAS docs](https://planetarycomputer.microsoft.com/docs/concepts/sas)
- MPC hosts a `sentinel-1-rtc` (radiometrically terrain-corrected) collection, which can be read with odc-stac. — [Tutorial: Read S1 RTC from MPC](https://e-marshall.github.io/cloud-open-source-geospatial-datacube-workflows/sentinel1/nbs/4_read_pc_data.html)
- Known open issues on MPC `sentinel-1-rtc` include #417 (proj:transform/bbox) and #404 (step changes in terrain correction). — [PlanetaryComputer GitHub issues](https://issues.ecosyste.ms/hosts/GitHub/repositories/microsoft%2FPlanetaryComputer/issues)
- Constellation status:
  - Sentinel-1C launched 5 Dec 2024 and Sentinel-1D in Nov 2025. — [Wikipedia: Sentinel-1C](https://en.wikipedia.org/wiki/Sentinel-1C); [CDSE: S1D user data opening](https://dataspace.copernicus.eu/node/3176)
  - From 9 Jun 2026, Sentinel-1C manoeuvred to a 6-day revisit relative to S1D, with nominal operations from 24 Jun 2026. — [ESA collgs: S1 orbital reconfiguration](https://collgs.esa.int/?p=8457); [CDSE](https://dataspace.copernicus.eu/node/3949)
  - The two-satellite revisit is 6 days at the equator. — [ESA facts](https://www.esa.int/Our_Activities/Observing_the_Earth/Copernicus/Sentinel-1/Facts_and_figures)
- Copernicus Data Space Ecosystem (CDSE) free "Copernicus General" account: Sentinel Hub gets 10,000 Processing Units per month and 300 per minute. Quotas reset monthly. Sentinel-1 GRD and SLC are available. — [CDSE PU calculator blog](https://dataspace.copernicus.eu/node/2602); [CDSE openEO credit usage](https://documentation.dataspace.copernicus.eu/APIs/openEO/credit_usage.html); [DLR CDSE page](https://www.dlr.de/en/eoc/research-transfer/projects-missions/cdse)
  - Some rate-limit figures, such as openEO at 12 requests/min with 2 concurrent requests, come only from third-party aggregators. — [apis.io ESA rate limits](https://apis.io/rate-limits/esa/esa-rate-limits/) (unverified)

**NASA POWER**
- No API key is mentioned. There are Temporal, Application, Validate and System APIs, and HTTP 429 is returned for too many requests. — [POWER API docs](https://power.larc.nasa.gov/docs/services/api/)
- Data sources and coverage:
  - Meteorology from MERRA-2 runs from 1981 at ½° × ⅝°. Solar data is at 1° × 1°.
  - MERRA-2 runs to within several months of real time. GEOS FP-IT fills the gap to within several days of real time.
  - Release 9 added hourly data for some parameters.
  - POWER also lists SMAP L4 soil moisture (~9 km, daily, from 31 Mar 2015) as a source.

  — [POWER methodology](https://power.larc.nasa.gov/docs/methodology/)
- POWER is much coarser than Open-Meteo (~50 km), so it adds little except a cross-check and long climatology.

**SMAP and ESA CCI soil moisture**
- SMAP L4 SPL4SMGP: 9 km EASE-Grid 2.0, surface and root-zone soil moisture, 3-hourly geophysical fields, starting 31 Mar 2015. The current version is v8 (v7 was removed from AppEEARS). It is accessible via NSIDC, AppEEARS and GEE, and needs an Earthdata login. — [NSIDC SPL4SMGP](https://nsidc.org/data/spl4smgp/versions/2); [LP DAAC alert: new SMAP L4 versions](https://www.earthdata.nasa.gov/data/alerts-outages/new-versions-smap-level-4-products-now-available-appeears); [MTRI AppEEARS how-to](https://www.mtu.edu/mtri/research/outreach/soil-moisture/smap-appeears-how-to.pdf); [GEE NASA_SMAP_SPL4SMGP_008](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008?hl=ja)
- SPL4SMGP latency averaged about 22,186 minutes (~15 days) in a 2015 JPL ingest analysis. That figure is old, and the current latency is unverified (see Gaps). — [JPL presentation](https://smap.jpl.nasa.gov/system/internal_resources/details/original/324_116-Leon.pdf)
- ESA CCI Soil Moisture v09.2 (ACTIVE, PASSIVE and COMBINED products) covers Nov 1978–31 Dec 2024. The v09.1 ACTIVE product was 0.25°. — [ESA CCI v09.2 ACTIVE](https://climate.esa.int/en/catalogue/2600f842cfeb481bb21f032a5741c353/); [Zenodo v09.2 validation report (Apr 2026)](https://zenodo.org/records/19565872); [CEDA catalogue](https://catalogue.ceda.ac.uk/uuid/2600f842cfeb481bb21f032a5741c353/)
  - This is useful for historical training and climatology, not for real-time use.

**Rainfall observations**
- GPM IMERG Early Run: 0.1°, half-hourly, with a minimum latency of about 4 h. The daily Early product (GPM_3IMERGDE V07) is available after the UTC day closes. It needs an Earthdata login. — [NASA GPM IMERG Early](https://gpm.nasa.gov/taxonomy/term/1357); [Earthdata GPM_3IMERGDE](https://www.earthdata.nasa.gov/es/data/catalog/ges-disc-gpm-3imergde-07)
- CHIRPS: the preliminary product has a ~2-day lag per pentad with automated QC only. The final product comes out in the third week of the following month. It is not confirmed whether this applies to CHIRPS v3. — [data.gov CHIRPS record](https://catalog.data.gov/harvest_record/d89b70f7-b72d-4f4e-a9bf-44f4848243ef/raw)
- IMD Pune gridded data:
  - Rainfall is at 0.25° from 1901 to present. Tmax/Tmin are at 1.0° from 1951.
  - Real-time daily rainfall is 0.25° and temperature 0.5°, accessible through the Python `imdlib` package or R `imdR`.
  - The imdpune.gov.in server is sometimes unavailable.

  — [imdlib docs](https://imdlib.readthedocs.io/en/latest/Usage.html); [imdR manual](https://cran.r-universe.dev/imdR/doc/manual.html)

**Indian sources**
- MOSDAC hosts a Soil Wetness Index (SWI) derived from a SMAP L-band time series, listed as Open Access, with files named `SWI_SMAP_I_YYYYMMD1_YYYYMMD2.tif`. INSAT-3D HEM rainfall is available as GeoTIFF. I found no confirmed INSAT-3DS soil-wetness product. — [MOSDAC node 2070](https://mosdac.gov.in/node/2070); [JAXA AFSIS training](https://www.eorc.jaxa.jp/SAFE/project/agromet/AFSIS-Training_20220709.pdf)
- VEDAS (ISRO SAC) offers soil moisture, rainfall, temperature and vegetation/crop monitoring. Since Oct 2019 it has published surface soil moisture, NDVI and other agromet products aggregated at block and district level. Krishi-DSS (launched Aug 2024) is built on VEDAS. — [ISRO VEDAS services](https://www.isro.gov.in/VedasServices.html); [J. Agrometeorology 2023 (DOAJ)](https://doaj.org/article/92b144004b9a4716a4fd64f7706b5aac); [YourStory Krishi-DSS](https://yourstory.com/2024/08/govt-launches-satellite-based-farm-decision-support-system)
- NRSC/Bhuvan lists an India soil moisture dataset from June 2013, downloadable via the Bhuvan portal. No API is documented. — [NRSC EOP geophysical land](https://www.nrsc.gov.in/EOP_geophysical_land/page_1)
- ISRO says NISAR will deliver 100 m soil moisture every 13 days across India. This is a forward-looking claim reported in the press. — [Daily Excelsior](https://www.dailyexcelsior.com/?p=2158267)

**Other sources**
- Google Earth Engine (GEE) non-commercial quota tiers started 27 Apr 2026:
  - **Community:** 150 EECU-hours/month, the default for verified non-commercial projects.
  - **Contributor:** 1,000 EECU-hours/month; needs a billing account but non-commercial use is not charged.
  - **Partner:** by application, with review taking weeks.
  - Non-commercial status must be reverified yearly. Splitting work across projects ("quota farming") violates the ToS.

  — [GEE noncommercial tiers](https://developers.google.com/earth-engine/guides/noncommercial_tiers); [Spatial Thoughts quota article](https://spatialthoughts.com/2026/02/09/gee-quota-monitoring/)
- Planet NICFI tropical mosaics left the NICFI programme on 24 Jan 2025 because the contract ended. Access was temporarily extended to about 1 Apr 2025, and GFW removed the imagery on 1 Apr 2025. — [Planet community](https://community.planet.com/tropical-basemaps-85/nicfi-satellite-data-program-prolongs-public-access-to-high-resolution-rainforest-satellite-images-6020); [GFW blog](https://www.globalforestwatch.org/blog/data-and-tools/planet-imagery-changes-gfw)
  - **Treat NICFI as deprecated.** It was also monthly 4.77 m forest-focused imagery and never a crop tool.

### Inferences
- **Highest return for the least work:** add these variables to the existing Open-Meteo calls:
  - `soil_moisture_0_to_1cm`, `soil_moisture_3_to_9cm`, `soil_moisture_9_to_27cm`, `soil_temperature_6cm`, `vapour_pressure_deficit`, `et0_fao_evapotranspiration`, `evapotranspiration`, and daily leaf-wetness probability.
  - The ERA5-Land archive (0.1°, from 1950) for training labels and climatology.
  - Ensemble API probability bands for the 7–15 day outlook.

  Waterlogging and saturated topsoil (soil moisture near field capacity for several days) combined with high RH and canopy closure maps directly onto Rhizoctonia aerial blight risk. Prolonged leaf wetness maps onto anthracnose and rust. Dry spells and high VPD favour whitefly build-up and therefore yellow mosaic. These are standard agronomic associations, and only the aerial blight thresholds are sourced above.
- **Sentinel-1 RTC on MPC is the single most valuable new satellite layer.** Kharif soybean (Jun–Oct) coincides with monsoon cloud, and Sentinel-2 can go weeks without a clear scene. VH/VV backscatter tracks canopy biomass and closure, which is an aerial blight precondition. Low VV after rain over flat fields indicates surface water or waterlogging, and SRTM slope plus TWI sharpen this. The 6-day revisit with S1C+S1D gives roughly 1–2 looks per week. The change is small: the same STAC client and signing, different collection id.
- Model rainfall (Open-Meteo) over Malwa can be biased during convective monsoon events. Ingesting IMERG Early (≈4 h, 0.1°) or IMD 0.25° real-time gridded rainfall as an "observed rain in last 7 days" feature should improve the lagged-rainfall predictors that the aerial blight literature emphasises.
- SMAP L4 at 9 km is coarser than Open-Meteo's model soil moisture grid. It adds value as an observation-constrained (assimilated) root-zone moisture and for validating Open-Meteo soil moisture, not for field-scale detail. For a hackathon, it is optional.
- NASA POWER is largely redundant with Open-Meteo. Use it only as a fallback or for climatology.
- IMD AAS/GKMS block advisories are best used as an authoritative "official advisory" overlay shown to farmers, and to validate the model, rather than as a numeric feature.

### Gaps
- Current (2026) SPL4SMGP v8 latency could not be confirmed. Only a 2015 ~15-day ingest figure was found, and NSIDC product pages should be checked. The SMAP L3 9 km enhanced (SPL3SMP_E) latency was not retrieved.
- Whether MPC `sentinel-1-rtc` has ingested Sentinel-1C/1D scenes, and its current update latency over India, could not be confirmed. Check the collection's most recent item dates for the Malwa bbox.
- No sourced hourly leaf-wetness duration product exists in any free API found. NASA POWER parameters (GWETTOP/GWETROOT/GWETPROF, T2MDEW) were not confirmed from the pages fetched.
- Soybean rust and anthracnose leaf-wetness hour thresholds were not retrieved in this pass.
- The ESA CCI soil moisture ICDR (near-real-time extension) latency was not found.
- I did not retrieve which Open-Meteo forecast model supplies soil moisture over India (the "best match" model is likely ECMWF IFS or GFS, but this is unverified).

## Q2. Exact access steps, cost, limits, and whether a hackathon team can get access within a day

### Takeaway
Same-day and free: Open-Meteo extras (no key), MPC Sentinel-1 (anonymous SAS), NASA POWER (no key), and NASA Earthdata for SMAP/IMERG/AppEEARS (instant self-registration). Also same-day: CDSE (email-verified account), IMD gridded rainfall via imdlib (no key, but the server is flaky), and MOSDAC open-access products (anonymous). GEE is likely same-day for a Community-tier non-commercial project, but cloud-project setup adds friction. Unlikely within a day: the IMD official API (registration plus nodal-officer approval) and MOSDAC registered datasets (account approval needed). Bhuvan and VEDAS have no documented public API.

### Cited Findings

**Open-Meteo**
- Free tier is non-commercial: 600/min, 5,000/hour, 10,000/day and 300,000/month (the monthly limit is not currently enforced). There is no uptime guarantee.
- Commercial plans are Standard 1M, Professional 5M and Enterprise 50M+ calls per month. Prices are not shown on the page. The Historical, climate, ensemble and satellite-radiation APIs require **Professional or higher** for commercial use.
- Data is licensed CC BY 4.0, and attribution is required.

— [Open-Meteo pricing](https://open-meteo.com/en/pricing)

**Microsoft Planetary Computer**
- Anonymous SAS token per collection; STAC is open. — [MPC SAS docs](https://planetarycomputer.microsoft.com/docs/concepts/sas)

**NASA POWER**
- No key mentioned; returns 429 when rate-limited. — [POWER API docs](https://power.larc.nasa.gov/docs/services/api/)

**NASA SMAP via AppEEARS / NSIDC**
- An Earthdata login is required. AppEEARS carries the full SPL3SMP, SPL3SMP_E and SPL4SMGP series from 31 Mar 2015. — [MTRI AppEEARS how-to](https://www.mtu.edu/mtri/research/outreach/soil-moisture/smap-appeears-how-to.pdf)
- SPL4SMGP is also in the GEE catalogue. — [GEE dataset](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008?hl=ja)

**CDSE**
- Every registered user defaults to the "Copernicus General" type, with 10,000 Sentinel Hub PU/month free. — [CDSE openEO credit usage](https://documentation.dataspace.copernicus.eu/APIs/openEO/credit_usage.html); [CDSE PU calculator](https://dataspace.copernicus.eu/node/2602); [CDSE FAQ](https://documentation.dataspace.copernicus.eu/FAQ.html)

**IMD official API**
- api.imd.gov.in describes "authenticated user onboarding with profile validation", key/JWT-based access, and Register/Login pages. It covers city forecasts, nowcasts, rainfall, marine bulletins and warnings. — [IMD API portal](https://api.imd.gov.in/)
- IMD's API document (mausam.imd.gov.in) directs organisations to the nodal officer (Dr. Sankar Nath, sankar.nath@imd.gov.in) and points to `api.imd.gov.in/public/api_reference.html`. — [IMD API doc PDF](https://mausam.imd.gov.in/Forecast/marquee_data/API_doc.pdf) (summarised via search snippet; the PDF text could not be extracted directly)
- An Aug 2025 RTI reply states IMD provides APIs free of charge for non-commercial use only. — [IMD RTI 211 (Jan 2026 listing)](https://internal.imd.gov.in/section/rti/rticases/20260112_rti_211.pdf)
- AWS/ARG station data has been restricted to designated users, and commercial use of AWS data is not permitted. — [Down To Earth](https://www.downtoearth.org.in/climate-change/imd-locking-up-its-awsarg-data-portal-hampers-public-weather-alerts-experts)

**IMD gridded data**
- Downloadable without a key via imdlib/imdR from imdpune.gov.in, which is "sometimes unavailable". — [imdR manual](https://cran.r-universe.dev/imdR/doc/manual.html); [imdlib](https://imdlib.readthedocs.io/en/latest/Usage.html)

**MOSDAC**
- Anonymous users can download open data only. Other data requires a SignUp form and account approval, after which ordering goes through the catalog app. API download support is via admin@mosdac.gov.in. — [MOSDAC data access](https://mosdac.gov.in/node/765); [MOSDAC 2025 brochure](https://www.nrsc.gov.in/sites/default/files/pdf/Brochures/MOSDAC_2025.pdf)

**GEE**
- New projects choose a tier at registration. Community tier has no extra requirements; Contributor needs billing enabled (non-commercial use is not charged); Partner takes weeks. — [GEE noncommercial tiers](https://developers.google.com/earth-engine/guides/noncommercial_tiers)

### Inferences
**Recommended hackathon order (all achievable in under a day)**
1. Add the Open-Meteo soil, ET, VPD and leaf-wetness variables, the ERA5-Land archive and the ensemble calls. This is code only.
2. Add MPC `sentinel-1-rtc`, computing VH, VV, the VH/VV ratio and a waterlogging flag. This is code only.
3. Register for NASA Earthdata (minutes) and pull IMERG Early daily rainfall plus, optionally, SMAP L4 via AppEEARS or OPeNDAP. Alternatively, use imdlib for IMD 0.25° rainfall with a cached fallback.
4. Optionally, register a CDSE account as a backup Sentinel-1/2 source if MPC throttles.

**Commercial and licensing caution**
- The free Open-Meteo, IMD API and GEE Community tier are all restricted to **non-commercial** use. A deployed FasalNetra that charges users would need Open-Meteo **Professional** (needed for the historical and ensemble APIs) and a GEE commercial licence.

**Defer or avoid for the hackathon**
- **IMD API:** expect email or nodal-officer back-and-forth and IP/profile validation. For the demo, link to or scrape the public AAS bulletin pages instead.
- **Bhuvan and VEDAS:** treat as visual references only.
- **Planet NICFI:** discontinued.

### Gaps
- The exact sign-up steps and typical approval turnaround for api.imd.gov.in, and whether district forecast or AAS endpoints are open to individual registrants, could not be confirmed. The API reference page was not retrievable.
- The GKMS/AAS block-level bulletin URLs and formats for Mandsaur, Indore and Ujjain were not researched in this pass.
- The Copernicus CDS (ERA5) API key process for the 2024+ CDS and the CHIRPS v3 latency were not retrieved. ERA5 via Open-Meteo covers most needs anyway.
- No documentation was found for a Bhuvan API key or a VEDAS public API.
- No official MPC statement on rate limits for anonymous SAS tokens was found.
