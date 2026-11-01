"""OpenAI vision calls, same cost rules as llm.py (cost-aware-llm-pipeline skill).

- Routing: fast model first; "unsure" or low-confidence answers are re-asked on the stronger model.
- Narrow retries: only rate limits, timeouts and server errors.
- Spend tracking: shared CostTracker from llm.py, so one budget covers every provider.
- Caching: instructions + reference images form a fixed prefix (OpenAI caches long identical prefixes
  automatically); the farmer's photo is always the last part.
"""
import base64
import json
import os
import time

from backend.app.services.vision import llm
from backend.app.services.vision.llm import CostRecord

FAST_MODEL = os.environ.get("OPENAI_VISION_MODEL_FAST", "gpt-4.1-mini")
STRONG_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4.1")
ESCALATE_BELOW = 0.6
MAX_RETRIES = 3
# USD per 1M tokens (input, output); check https://openai.com/api/pricing before relying on the totals
PRICES: dict[str, tuple[float, float] | None] = {"gpt-4.1-mini": (0.40, 1.60), "gpt-4.1": (2.00, 8.00)}


def api_key() -> str:
    """The team's .env spells it OPEN_AI_API_KEY; the SDK's own name works too."""
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_API_KEY") or ""


def _image(jpeg: bytes, detail: str) -> dict:
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    return {"type": "image_url", "image_url": {"url": url, "detail": detail}}


def build_messages(prompt: str, refs: list[tuple[str, bytes]], jpeg: bytes) -> list[dict]:
    parts: list[dict] = [{"type": "text", "text": prompt}]
    for label, ref in refs:
        parts += [{"type": "text", "text": f"Reference example, label = {label}:"}, _image(ref, "low")]
    parts += [{"type": "text", "text": "Now classify this farmer's photo:"}, _image(jpeg, "high")]
    return [{"role": "user", "content": parts}]


def _schema(labels: list[str]) -> dict:
    return {"name": "leaf_check", "strict": True, "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "symptoms_seen": {"type": "string"},
            "label": {"type": "string", "enum": labels},
            "confidence": {"type": "number"},
            "severity": {"type": "integer"},
            "whitefly_visible": {"type": "boolean"},
        },
        "required": ["symptoms_seen", "label", "confidence", "severity", "whitefly_visible"],
    }}


def _call(model: str, messages: list[dict], labels: list[str]) -> tuple[dict, CostRecord]:
    import openai

    client = openai.OpenAI(api_key=api_key(), timeout=40)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=0,
                response_format={"type": "json_schema", "json_schema": _schema(labels)})
            break
        except (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    u = resp.usage
    tin, tout = (u.prompt_tokens if u else 0), (u.completion_tokens if u else 0)
    price = PRICES.get(model)
    cost = (tin * price[0] + tout * price[1]) / 1e6 if price else None
    return json.loads(resp.choices[0].message.content), CostRecord(model, tin, tout, cost)


def ask(messages: list[dict], labels: list[str]) -> dict:
    """Fast model first; escalate when it is unsure, unless the budget is spent."""
    out, rec = _call(FAST_MODEL, messages, labels)
    llm.tracker = llm.tracker.add(rec)
    out["model"] = FAST_MODEL
    if (out["label"] == "unsure" or out["confidence"] < ESCALATE_BELOW) and not llm.tracker.over_budget \
            and STRONG_MODEL != FAST_MODEL:
        out, rec = _call(STRONG_MODEL, messages, labels)
        llm.tracker = llm.tracker.add(rec)
        out.update(model=STRONG_MODEL, escalated=True)
    return out
