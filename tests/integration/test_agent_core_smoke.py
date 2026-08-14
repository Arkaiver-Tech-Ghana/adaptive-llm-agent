"""Automated version of the PRD's "tested via CLI" requirement: exercises
the exact code path the CLI does, against the real Google Gemini API and the
real KampusCrave Business Config.
"""

import os
from pathlib import Path

import pytest

from adaptive_agent.agent_core import load_agent_core

BUSINESS_CONFIG = Path(__file__).parents[2] / "businesses" / "kampuscrave" / "business.yaml"

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="requires a real GOOGLE_API_KEY (kampuscrave's Business Config uses the google provider)",
)
def test_kampuscrave_answers_menu_question_from_context():
    agent = load_agent_core(BUSINESS_CONFIG)
    reply = agent.respond("What's on the menu?")
    assert reply
    assert "burger" in reply.lower()
