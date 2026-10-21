"""Regression tests for two bugs found during live testing on a real device.

1. The local 7B model flagged `danger_to_people` on almost every report, which
   pinned every priority to the critical floor (75) and made the prioritisation
   engine meaningless: seven of eight seeded reports scored exactly 75.0.
2. The assistant told a user to call 15, the French emergency number, for a
   collapsed school roof, instead of the Tunisian 198 / 190.

Both are failures of trusting a small model's judgement, so both fixes make the
deterministic data authoritative and leave the model only able to agree with it.
"""
import asyncio

from app.ai.assistant import SYSTEM_PROMPT, rule_triage, triage

# What the over-confident model returns for anything at all.
MODEL_CRIES_DANGER = {
    "category": "waste",
    "suggested_urgency": 80,
    "summary": "Poubelles qui debordent.",
    "danger_to_people": True,
}


class FakeLLM:
    """A provider whose verdict we control, so no network is involved."""

    enabled = True
    provider = "fake"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def complete_json(self, system: str, user: str) -> dict:  # noqa: ARG002
        return dict(self._payload)


def _triage(text: str, payload: dict) -> dict:
    return asyncio.run(triage(text, llm=FakeLLM(payload)))


def test_model_cannot_raise_the_danger_flag_alone():
    """Overflowing bins are not a danger to people, whatever the model claims."""
    out = _triage("Les poubelles debordent depuis plusieurs jours", MODEL_CRIES_DANGER)
    assert out["danger_to_people"] is False


def test_danger_flag_stands_when_the_keywords_agree():
    """A fallen electrical cable is a real danger and must stay flagged."""
    out = _triage("Un cable electrique est tombe dans la rue", MODEL_CRIES_DANGER)
    assert out["danger_to_people"] is True


def test_model_can_still_clear_the_flag():
    """The guard only removes danger; the model is still trusted to say 'no'."""
    calm = dict(MODEL_CRIES_DANGER, danger_to_people=False)
    out = _triage("Un cable electrique est tombe dans la rue", calm)
    assert out["danger_to_people"] is False


def test_rule_triage_leaves_ordinary_waste_unflagged():
    assert rule_triage("Sacs de dechets abandonnes sur le trottoir")["danger_to_people"] is False


def test_prompt_carries_the_tunisian_emergency_numbers():
    for number in ("198", "190", "197", "193"):
        assert number in SYSTEM_PROMPT, f"{number} missing from the assistant prompt"


def test_prompt_rules_out_the_french_numbers():
    assert "FAUX en Tunisie" in SYSTEM_PROMPT


class RecordingLLM(FakeLLM):
    """Captures the prompt it is given, so the test can assert on it."""

    def __init__(self, payload: dict) -> None:
        super().__init__(payload)
        self.prompts: list[str] = []

    async def complete_json(self, system: str, user: str) -> dict:  # noqa: ARG002
        self.prompts.append(user)
        return dict(self._payload)


def test_triage_summary_is_asked_for_in_the_app_language():
    """The summary is shown straight back to the citizen, so it has to be in the
    language they are reading the app in.

    Regression: the prompt hardcoded "resume factuel en francais", so a report
    typed in English came back summarised in French however the app was set.
    An unknown or missing language still falls back to French.
    """
    for lang, expected in [("en", "anglais"), ("ar", "arabe"), ("fr", "francais"),
                           (None, "francais"), ("", "francais"), ("zz", "francais"),
                           ("EN", "anglais"), (" ar ", "arabe")]:
        llm = RecordingLLM(MODEL_CRIES_DANGER)
        asyncio.run(triage("a large pothole in the middle of the road", llm=llm, lang=lang))
        assert f"en {expected}," in llm.prompts[0], (lang, llm.prompts[0])
