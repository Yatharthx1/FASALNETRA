"""Cost-aware routing: cheap model first, escalate only when unsure, stop escalating over budget."""
import json

import pytest

from backend.app.services.vision import llm


@pytest.fixture
def fake_call(monkeypatch):
    answers: dict[str, dict] = {}
    calls: list[str] = []

    def _call(model, contents, config):
        calls.append(model)
        return json.dumps(answers[model]), llm.CostRecord(model, 1000, 50, 0.01)

    monkeypatch.setattr(llm, "_call", _call)
    monkeypatch.setattr(llm, "tracker", llm.CostTracker(budget_usd=1.0))
    return answers, calls


def test_confident_fast_answer_is_not_escalated(fake_call):
    answers, calls = fake_call
    answers[llm.FAST_MODEL] = {"label": "yellow_mosaic", "confidence": 0.9}
    out = llm.ask([], None, json.loads)
    assert calls == [llm.FAST_MODEL] and out["model"] == llm.FAST_MODEL


@pytest.mark.parametrize("fast", [{"label": "unsure", "confidence": 0.9}, {"label": "fungal", "confidence": 0.4}])
def test_unsure_or_weak_answer_escalates(fake_call, fast):
    answers, calls = fake_call
    answers[llm.FAST_MODEL] = fast
    answers[llm.STRONG_MODEL] = {"label": "fungal", "confidence": 0.8}
    out = llm.ask([], None, json.loads)
    assert calls == [llm.FAST_MODEL, llm.STRONG_MODEL] and out["escalated"] is True


def test_no_escalation_once_budget_is_spent(fake_call, monkeypatch):
    answers, calls = fake_call
    monkeypatch.setattr(llm, "tracker", llm.CostTracker(budget_usd=0.0))
    answers[llm.FAST_MODEL] = {"label": "unsure", "confidence": 0.2}
    llm.ask([], None, json.loads)
    assert calls == [llm.FAST_MODEL]


def test_tracker_is_immutable():
    t0 = llm.CostTracker(budget_usd=1.0)
    t1 = t0.add(llm.CostRecord("m", 10, 5, 0.5))
    assert t0.records == () and t1.total_usd == 0.5 and t1.tokens == 15
