"""Cost-aware vision LLM calls (cost-aware-llm-pipeline skill).

- Routing: every photo goes to the fast model first; only "unsure" or low-confidence
  answers are re-asked on the stronger model.
- Narrow retries: only rate limits and server errors are retried; bad requests fail fast.
- Spend tracking: immutable records with a session budget; the pipeline stops escalating
  (falls back to the fast answer) once the budget is spent.
- Caching: the instruction + reference images are a fixed prefix sent first, so the
  provider's implicit prompt cache can reuse it; the farmer's photo is always last.
"""
import os
import time
from dataclasses import dataclass

FAST_MODEL = os.environ.get("VISION_MODEL_FAST", "gemini-2.5-flash-lite")
STRONG_MODEL = os.environ.get("VISION_MODEL", "gemini-2.5-flash")
ESCALATE_BELOW = 0.6
MAX_RETRIES = 3

# USD per 1M tokens (input, output). Fill from the provider's current pricing page; None = track tokens only.
PRICES: dict[str, tuple[float, float] | None] = {FAST_MODEL: None, STRONG_MODEL: None}


@dataclass(frozen=True, slots=True)
class CostRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


@dataclass(frozen=True, slots=True)
class CostTracker:
    budget_usd: float
    records: tuple[CostRecord, ...] = ()

    def add(self, record: CostRecord) -> "CostTracker":
        return CostTracker(self.budget_usd, (*self.records, record))

    @property
    def total_usd(self) -> float:
        return sum(r.cost_usd or 0.0 for r in self.records)

    @property
    def tokens(self) -> int:
        return sum(r.input_tokens + r.output_tokens for r in self.records)

    @property
    def over_budget(self) -> bool:
        return self.total_usd > self.budget_usd


tracker = CostTracker(budget_usd=float(os.environ.get("VISION_BUDGET_USD", "5")))


def _retryable(exc: Exception) -> bool:
    from google.genai import errors
    return isinstance(exc, errors.ServerError) or (isinstance(exc, errors.ClientError) and exc.code == 429)


def _call(model: str, contents, config) -> tuple[str, CostRecord]:
    from google import genai

    client = genai.Client(api_key=os.environ.get("VISION_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            break
        except Exception as exc:
            if not _retryable(exc) or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    usage = resp.usage_metadata
    tin, tout = (usage.prompt_token_count or 0), (usage.candidates_token_count or 0)
    price = PRICES.get(model)
    cost = (tin * price[0] + tout * price[1]) / 1e6 if price else None
    return resp.text, CostRecord(model, tin, tout, cost)


def ask(contents, config, parse) -> dict:
    """Fast model first; escalate when it is unsure, unless the budget is spent."""
    global tracker
    text, rec = _call(FAST_MODEL, contents, config)
    tracker = tracker.add(rec)
    out = {**parse(text), "model": FAST_MODEL}
    if (out["label"] == "unsure" or out["confidence"] < ESCALATE_BELOW) and not tracker.over_budget \
            and STRONG_MODEL != FAST_MODEL:
        text, rec = _call(STRONG_MODEL, contents, config)
        tracker = tracker.add(rec)
        out = {**parse(text), "model": STRONG_MODEL, "escalated": True}
    return out
