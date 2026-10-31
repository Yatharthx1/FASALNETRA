# Kisan Call Centre (KCC) query data: soybean in Madhya Pradesh. Access paths and characteristics

Research date: 2026-11-01. Method note: in this session data.gov.in returned HTTP 403 to automated fetch. kcc-chakshu / iasri.res.in refused the connection. krishi.icar.gov.in did not resolve. Live API test calls and Hugging Face card fetches were blocked by the agent's permission layer. Many details below therefore come from the AIKosh page (fetched directly) and from search-result snippets. Each claim is labelled with how well it was verified.

## 1. AIKosh dataset "Kisan Call Centre - Transcripts of farmers queries and answers"

### Takeaway
AIKosh does not host the data itself. Its entry is a redirect stub that points to the data.gov.in resource. It has no file size, no year range and no API. Use data.gov.in (or KCC-CHAKSHU) instead.

### Cited Findings
- Title: "Kisan Call Centre - Transcripts of farmers queries and answers". Described as district-wise and month-wise details of farmer queries and FTA (Farm Tele Advisor) answers. — [AIKosh dataset page](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)
- Hosting is "Redirected" to https://www.data.gov.in/resource/kisan-call-centre-kcc-transcripts-farmers-queries-answers. Dataset type is "Structured". The format is not stated. File size is 0 or not listed. Year range is "N.A.". Granularity and frequency are "Static". Coverage is India. — [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)
- Licence: Open Government License – India. Visibility: "Open", with a "Download Dataset" button. The page does not say whether login is needed. No API is mentioned. — [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)
- Author: Ministry of Agriculture & Farmers Welfare (DA&FW). Entry date 24/02/2025. Activity: 13 downloads, 3,046 redirects, 15,768 views. — [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)
- The page links several KisanSLM models (GGUF builds on Gemma, Llama and Qwen; Apache-2.0) as fine-tuned on this dataset. A separate AIKosh model "kisan_chat" (Think Evolve Labs, Apache 2.0) is fine-tuned on KCC data. — [AIKosh dataset](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html); [AIKosh kisan_chat](https://aikosh.indiaai.gov.in/home/models/details/kisan_chat.html)

### Inferences
- An AIKosh login probably adds nothing: "Hosting: Redirected" means the "Download" button sends users to data.gov.in. A developer should go straight to data.gov.in.

### Gaps
- The AIKosh login and sign-up flow was not tested. Whether AIKosh adds a mirrored file (CSV or Parquet) is unconfirmed. The page shows size 0, which suggests it does not.

## 2. data.gov.in resources and the api.data.gov.in API

### Takeaway
The current data.gov.in resource "kisan-call-centre-kcc-transcripts-farmers-queries-answers" has fields that include StateName and DistrictName. According to search snippets of the page, it currently reports that no API exists for it and offers a "Request API" button (contact ndsap@gov.in). A Hugging Face derivative cites a data.gov.in resource UUID, cef25fe2-9231-4128-8aec-2c948fedd43f, as its source. The general API pattern is https://api.data.gov.in/resource/{uuid}?api-key=KEY&format=json&offset=&limit=&filters[Field]=value. Neither the UUID nor the API pattern could be live-tested here.

### Cited Findings
- The resource page lists StateName and DistrictName among its fields. It says the API for this resource does not exist and asks users to click "Request API" or email ndsap@gov.in. — search-result summary of [data.gov.in resource page](https://www.data.gov.in/resource/kisan-call-centre-kcc-transcripts-farmers-queries-answers). (Direct fetch returned HTTP 403, so this is not verified first-hand.)
- Catalogue description: "district wise - month wise details of queries asked by farmers and answers given by FTAs". — [data.gov.in resource](https://www.data.gov.in/resource/kisan-call-centre-kcc-transcripts-farmers-queries-answers); [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html)
- The Hugging Face dataset judicialmind/KCC-Pairs names data.gov.in resource cef25fe2-9231-4128-8aec-2c948fedd43f as its source. — search snippet of [HF KCC-Pairs](https://huggingface.co/datasets/judicialmind/KCC-Pairs). (The card could not be fetched.)
- API key: register on data.gov.in, then copy the key from "My Account" after logging in. The key may only work after activation through an emailed link; otherwise expect 403 errors. — [CRAN datagovindia README](https://ftp.eenet.ee/pub/cran/web/packages/datagovindia/readme/README.html); [datagovindia GitHub](https://github.com/addypy/datagovindia)
- Request format: the key goes in the query string (`api-key=`), with `offset`, `limit` and field filters combined with AND. — [R-bloggers 2014 (old)](https://www.r-bloggers.com/2014/04/accessing-open-data-portal-india-using-apis/); [apis-list entry](https://github.com/apis-list/apis-list/blob/main/apis/open-government-india/open-government-india.md)
- Row limits: a 2014 tutorial reports 100 records per call. Another third-party source repeats a ~100-row cap on /resource but cites up to 1,000 per page on /lists. These are old or unverified. — [R-bloggers 2014](https://www.r-bloggers.com/2014/04/accessing-open-data-portal-india-using-apis/); [Apify data.gov.in scraper](https://apify.com/themineworks/india-data-gov-scraper)
- Python and R wrappers exist (`datagovindia` on PyPI/CRAN) for search, metadata and resource fetch, and they need an API key. — [PyPI datagovindia](https://pypi.org/project/datagovindia/0.1); [GitHub addypy/datagovindia](https://github.com/addypy/datagovindia)

### Inferences
- Suggested developer path (unverified, so test it first):
  1. Register at data.gov.in, activate by email, and copy the API key from My Account.
  2. Call `GET https://api.data.gov.in/resource/cef25fe2-9231-4128-8aec-2c948fedd43f?api-key=KEY&format=json&limit=1` to check that the resource is API-enabled and to read the `field` array, which gives the exact column ids.
  3. If it works, filter with `&filters[StateName]=MADHYA PRADESH` and, if supported, `&filters[DistrictName]=MANDSAUR` (match the case used in the data; KCC data has historically been upper-case). Filter on Crop locally, because the crop spelling varies ("Soybean", "Soyabean", "SOYBEAN"). Page with `offset` in steps of `limit`.
  4. If the API is disabled (as the resource page snippet suggests), use the CSV download on the resource page, or use "Request API" or ndsap@gov.in.
- The field names the task proposed (Season, Sector, Category, Crop, QueryType, QueryText, KccAns, StateName, DistrictName, BlockName, CreatedOn) match the long-standing KCC schema as I remember it. Only StateName and DistrictName are confirmed from a source here. Read the API `field` array before hard-coding names.
- From background knowledge, not verified this session: data.gov.in historically published KCC data as many per-state, per-month resources (e.g. "Kisan Call Centre (KCC) query data … Madhya Pradesh … <Month Year>"). In that case each month has its own resource UUID, and you need the catalog listing to enumerate them.

### Gaps
- Confirmed date coverage of the data.gov.in resource (start/end) and its lag behind the present. Not obtained because of the 403.
- Current per-call limit and rate limits of api.data.gov.in. Only 2014 and third-party figures were found.
- Whether resource cef25fe2… is currently API-enabled. The live call was not permitted in this session.

## 3. KCC-CHAKSHU portal (kcc-chakshu.icar.gov.in)

### Takeaway
KCC-CHAKSHU is ICAR-IASRI's analytics portal over the full KCC archive (over 40 million preprocessed queries). ICAR researchers use it as the primary data source in published state-level KCC studies. No public export or API documentation was found. Access terms are unknown, and the server refused connections from this environment.

### Cited Findings
- The name stands for "Collated Historically Aggregated Knowledge-based System with Hypertext User-interface". It is an ICAR-IASRI initiative giving access to over 40 million preprocessed farmer queries plus data-driven insights for policymakers and researchers. — search snippet of [IASRI project PDF](https://iasri.res.in/API/Content/UploadContent/638953620285071208.pdf). (The PDF could not be fetched: ECONNREFUSED.)
- The IJEE Rajasthan study used KCC data "obtained from the KCC-CHAKSHU portal (https://kcc-chakshu.icar.gov.in/)". Fields included call date and time, caller location to district level, crop and query nature. It covered over 4 million calls from 2009 onwards. — [IJEE Rajasthan paper](https://epubs.icar.org.in/index.php/IJEE/article/view/146208); [PDF](https://epubs.icar.org.in/index.php/IJEE/article/download/146208/53554/463391)
- The Haryana study (Godara et al., IJEE) analysed 26.8 lakh calls from January 2009 to May 2024, including temporal and geospatial analysis. This means the CHAKSHU-held data ran to at least May 2024. — [IJEE Haryana](https://epubs.icar.org.in/index.php/IJEE/article/view/156241); [KRISHI record](https://krishi.icar.gov.in/ohs-2.3.1/index.php/record/view/941824)

### Inferences
- CHAKSHU probably holds more recent data (into 2024) than data.gov.in. Bulk exports probably need a request to ICAR-IASRI (Samarth Godara's group, the Division of Computer Applications), not a public API.

### Gaps
- Whether the portal requires login, offers CSV export or has an API. The site could not be reached.

## 4. Mirrors: Hugging Face, Kaggle, GitHub

### Takeaway
The largest mirror is the gated Hugging Face dataset judicialmind/KCC-Pairs (about 5M Q&A pairs, cleaned and with PII removed). It is built for QA and probably lacks per-query date and district. There is also an aggregated KCC panel (2009–2025, small cells suppressed) inside judicialmind/BharatDistrictPanel. KisanVaani datasets are generic agri-QA and are not confirmed to be KCC-derived. No authoritative Kaggle mirror was found.

### Cited Findings
- judicialmind/KCC-Pairs: 4,996,402 question-answer pairs and 502,060 question-question pairs. Cleaned, de-duplicated and with PII removed. Gated: you accept the terms and log in with the HF CLI. Source given as data.gov.in resource cef25fe2-9231-4128-8aec-2c948fedd43f. The card warns that answers may be outdated or wrong. — search snippet of [HF KCC-Pairs](https://huggingface.co/datasets/judicialmind/KCC-Pairs)
- judicialmind/BharatDistrictPanel includes a KCC entry built from call logs as category counts, with cells under 10 suppressed, covering 2009–2025. — search snippet of [HF BharatDistrictPanel](https://huggingface.co/datasets/judicialmind/BharatDistrictPanel)
- KisanVaani/agriculture-qa-english-only: Parquet, 10K–100K rows. Its source is not stated as KCC. — [HF KisanVaani](https://huggingface.co/datasets/KisanVaani/agriculture-qa-english-only/tree/refs%2Fconvert%2Fparquet/default/train)
- A GitHub student project, "Data-Analysis-of-Farmer-query", mines KCC data (association rules, e.g. paddy plant-protection issues in Haryana). It is not peer-reviewed. — [GitHub (mirror link)](https://github.meowingcats01.workers.dev/akshitkh47612/Data-Analysis-of-Farmer-query)

### Inferences
- If BharatDistrictPanel's KCC counts are district × month × category, they may be the fastest route to monthly (not weekly) query volumes for the eight MP districts. Check its schema.
- KCC-Pairs may not keep CreatedOn or DistrictName, which limits it for timing analysis. Check its columns.

### Gaps
- Exact columns and the latest date in KCC-Pairs and BharatDistrictPanel. The cards could not be fetched.
- No Kaggle KCC dataset was found in the searches.

## 5. Data characteristics relevant to pest-surge analysis

### Takeaway
The records carry call date, district, crop and query type, which is enough to build weekly time series of soybean Plant Protection queries by MP district. MP-specific volumes and quality metrics were not found in a citable source.

### Cited Findings
- KCC records include call date and time, caller district, crop and query nature. Categorising calls by crop and query type allows targeted support. — [IJEE Rajasthan](https://epubs.icar.org.in/index.php/IJEE/article/view/146208)
- The KCC scheme has run since 2004 (toll-free 1800-180-1551), and the archive goes back to 2009 in the ICAR analyses. — [mKisan About KCC](https://mkisan.gov.in/Home/AboutKCC); [IJEE Haryana](https://epubs.icar.org.in/index.php/IJEE/article/view/156241)
- KCC-Pairs warns that answers may be out of date or wrong. Treat KccAns as noisy. — [HF KCC-Pairs](https://huggingface.co/datasets/judicialmind/KCC-Pairs)
- MP KCC history: ISAP ran KCC in MP, with about 20,000 calls a month reported around 2009. This figure is old. — [Manthan Award 2009](https://manthanaward.org/?p=6322)
- An impact study of KCC in MP exists in IJEE. — [IJEE MP KCC impact](https://epubs.icar.org.in/index.php/IJEE/article/view/128984)

### Inferences
- The following is from background knowledge, not verified this session. QueryText is a short summary the agent types in English or romanised Hindi (Hinglish), often misspelt, e.g. "asking about control of girdle beetle in soybean" or "Information regarding white fly". Use fuzzy keyword matching (girdle/gardle, semilooper/semi looper/green caterpillar, whitefly/safed makkhi, yellow mosaic/YMV/peela, spodoptera/tobacco caterpillar/army worm). Crop spelling varies (Soybean/Soyabean). Weather and market queries are mixed in with pest queries, so filter on QueryType = "Plant Protection".
- Publication lag on data.gov.in may run to years. ICAR's CHAKSHU-based studies reach May 2024, but the data.gov.in coverage end date could not be confirmed.

### Gaps
- Soybean query counts for MP or the eight districts. No citable figure was found.
- A documented share of Plant Protection queries for soybean.

## 6. Published analyses of KCC soybean pest-query timing

### Takeaway
One ICAR paper analyses KCC data specifically for soybean, among other edible oil crops: Godara et al. 2024. Only its abstract was accessible, and no week- or month-level soybean pest peaks from KCC were found. Field-entomology studies (not KCC) put sucking-pest and defoliator peaks in late August to September.

### Cited Findings
- Godara S., Kumar R., Jha G.K., Bana R.S., Choudhary R.L., Marwaha S., Parsad R., Singh D., Kumar R. (2024). "Analysing Indian farmers' information needs on edible oil crops using Kisan Call Center data". Covers groundnut, mustard and soybean, with queries categorised into agronomic practices, pest management, market information and other categories. Reports notable geographical variation in query volumes. Journal: Journal of Oilseed Brassica 15(2):189–198 per one snippet, with an epubs JOB article id of 156744. — [KRISHI record](https://krishi.icar.gov.in/ohs-2.3.1/index.php/record/view/940744); [epubs JOB](https://epubs.icar.org.in/index.php/JOB/article/view/156744)
- Non-KCC field data: in a Rajasthan study, jassid, whitefly and stem fly incidence began in the 2nd week of August and peaked from late August to September. Tobacco caterpillar (Spodoptera) and grey weevil peaked in the 4th week of September. — search snippet of [Rajasthan soybean pest study (kiran.nic.in)](https://www.kiran.nic.in/pdf/IJHF/Vol_31_1/9.pdf)
- ICAR-NRSI Indore publishes kharif soybean pest advisories (2025) covering defoliators, whitefly and stem borers. — [Global Agriculture summary](https://www.global-agriculture.com/farming-agriculture/pest-and-disease-management-in-soybean-for-high-yield-kharif-2025-recommended-agrochemicals/)

### Inferences
- Expected KCC soybean Plant Protection peaks in MP are probably late July to September (SMW 30–38). They would follow field-incidence peaks with little lag, since farmers call when they see symptoms. This is a hypothesis to test, not a cited finding.

### Gaps
- No published week- or month-level peaks of KCC soybean pest queries for MP (whitefly/YMV, girdle beetle, semilooper, Spodoptera) were found. The full text of Godara et al. 2024 was unreachable.
