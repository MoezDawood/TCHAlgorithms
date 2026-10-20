"""Load the bound TCH PDF as the agent's clinical context."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]


def load_agent(agent_json: Path) -> dict:
    return json.loads(agent_json.read_text())


def bound_pdf_text(agent: dict) -> str:
    path = ROOT / agent["source"]["pdf"]
    doc = fitz.open(path)
    parts = []
    for number, page in enumerate(doc, start=1):
        parts.append(f"\n\n--- page {number} ---\n")
        parts.append(page.get_text("text"))
    doc.close()
    return "".join(parts).strip()


def messages(agent: dict, hook_request: dict) -> list[dict]:
    """Messages for a model call. The PDF text is the clinical source."""
    standard = bound_pdf_text(agent)
    context = {
        "hook": hook_request.get("hook"),
        "hookInstance": hook_request.get("hookInstance"),
        "context": hook_request.get("context", {}),
        "prefetch": hook_request.get("prefetch", {}),
    }
    return [
        {"role": "system", "content": agent["systemPrompt"]},
        {
            "role": "user",
            "content": (
                "EPIC CDS HOOK REQUEST\n"
                + json.dumps(context, indent=2)
                + "\n\nBOUND STANDARD\n"
                + standard
                + "\n\nReturn one CDS Hooks response. If the patient is outside this standard, return {\"cards\": []}."
            ),
        },
    ]
