# FasalNetra

PS9 crop-health entry, AI Manthan 2.0 (Indore, 31 Oct 2026). Spec: `../FasalNetra_Full_Chat_Record.md` and `FasalNetra_PRD.md` (README is outdated).

## Skills: always apply the matching one

Skills live in `.claude/skills/`. When a request names no skill, pick from this map, read its `SKILL.md`, follow it, and say which one was used.

| Task | Skill(s) |
|---|---|
| FastAPI routes, schemas, DI, startup | `fastapi-patterns`, `python-patterns` |
| Any Python module or script | `python-patterns` |
| Backend tests | `python-testing` |
| Vision / voice LLM prompts | `prompt-optimizer` |
| LLM calls, caching, model choice, budget | `cost-aware-llm-pipeline` |
| React components and state | `react-patterns` |
| Vite config, env, proxy, build | `vite-patterns` |
| Look and feel of any screen | `frontend-design-direction`, `make-interfaces-feel-better`, `landing-page-design` (visual rules only) |
| Low-literacy farmer UI, Didi console | `frontend-a11y` |
| Hindi strings / locale files | `i18n-sync` |
| Before saying anything is done | `verification-loop` |
| Pitch deck | `frontend-slides` |

## Layout

- `backend/app/services/` — advisory (ICAR-NSRI table), risk (Open-Meteo + rules), mapping (Sentinel-2 grid), vision (LLM + CLIP), evidence (vote fusion), missions
- `scripts/` — `fetch_field_data.py` (cache S2/DEM/soil), `eval_vision.py`, `backtest_mandsaur.py`
- `data/processed/demo/` — cached satellite + terrain for the demo field; never call those APIs live in the demo

## Rules

- Spray doses come only from `data/seed/advisory_table.json`; the LLM never invents one.
- Say "shak" / "suspected", never a certain diagnosis. Weather rules are provisional until checked against the paper.
- Run from `FASALNETRA/`: `uvicorn backend.app.main:app --reload`, `cd frontend && npm run dev`.
