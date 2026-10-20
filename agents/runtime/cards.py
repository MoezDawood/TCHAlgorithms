"""CDS Hooks cards for the draft services.

The draft card does not give a treatment recommendation. It tells Epic which
standard matched the registration and points the clinician at the published PDF.
Treatment cards are produced by a model using runtime.knowledge.messages, after
clinical review.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]


def all_agents() -> list[dict]:
    agents = []
    for path in sorted((AGENTS / "standards").glob("*/agent.json")):
        agents.append(json.loads(path.read_text()))
    return agents


def by_id(agent_id: str) -> dict | None:
    for agent in all_agents():
        if agent["id"] == agent_id:
            return agent
    return None


def discovery() -> dict:
    return json.loads((AGENTS / "cds-services.json").read_text())


def draft_card(agent: dict) -> dict:
    """Wiring card. Safe to return before a model is attached."""
    return {
        "cards": [
            {
                "uuid": str(uuid.uuid4()),
                "summary": agent["cardSummary"][:140],
                "indicator": "info",
                "detail": (
                    f"**Draft agent `{agent['id']}`.** Clinical review is still required.\n\n"
                    f"{agent['mission']}\n\n"
                    f"**Inclusion.** {agent['population']['inclusion']}\n\n"
                    f"**Exit.** {agent['population']['exclusion']}\n\n"
                    "This card does not recommend a dose or an order. "
                    "The published PDF is the source. A model answer has to quote that PDF "
                    "and stay unsigned until a clinician accepts it."
                ),
                "source": {
                    "label": f"Texas Children's EBOC — {agent['title']}",
                    "url": agent["source"]["sourceUrl"],
                },
                "suggestions": [],
                "links": [
                    {
                        "label": "Open the published TCH PDF",
                        "url": agent["source"]["sourceUrl"],
                        "type": "absolute",
                    }
                ],
            }
        ]
    }
