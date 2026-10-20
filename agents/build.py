"""Build one Epic CDS Hooks agent folder per TCH clinical standard."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_entries import ENTRIES, PREFETCH

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = ROOT / "clinical-standards"
AGENTS = ROOT / "agents"
PREAMBLE = (AGENTS / "shared" / "preamble.md").read_text().strip()

QUERIES = {
    "patient": "Patient/{{context.patientId}}",
    "encounter": "Encounter/{{context.encounterId}}",
    "conditions": "Condition?patient={{context.patientId}}&clinical-status=active",
    "allergies": "AllergyIntolerance?patient={{context.patientId}}",
    "medications": "MedicationRequest?patient={{context.patientId}}&status=active,draft&_count=50",
    "vitals": "Observation?patient={{context.patientId}}&category=vital-signs&_sort=-date&_count=25",
    "labs": "Observation?patient={{context.patientId}}&category=laboratory&_sort=-date&_count=40",
    "procedures": "Procedure?patient={{context.patientId}}&_sort=-date&_count=20",
    "encounters": "Encounter?patient={{context.patientId}}&_sort=-date&_count=5",
}

PAGE = "https://www.texaschildrens.org/patients-families/safety-and-outcomes/clinical-standards"
HOOKS = {
    "patient-view",
    "encounter-start",
    "encounter-discharge",
    "order-select",
    "order-sign",
    "appointment-book",
}


def pdf_text(path: Path) -> str:
    doc = fitz.open(path)
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    text = re.sub(r"©\s*\d{4}\s*Texas Children[’']s Hospital", " ", text)
    return text


def section(text: str, starts: list[str], stops: list[str], limit: int = 900) -> str:
    low = text.lower()
    start = -1
    label = ""
    for item in starts:
        i = low.find(item.lower())
        if i != -1 and (start == -1 or i < start):
            start = i
            label = item
    if start < 0:
        return ""
    rest = text[start:]
    low_rest = rest.lower()
    end = len(rest)
    for item in stops:
        j = low_rest.find(item.lower(), len(label) + 2)
        if j != -1:
            end = min(end, j)
    chunk = rest[:end]
    chunk = chunk.replace("\uf0b7", "; ").replace("•", "; ").replace("", "; ")
    chunk = re.sub(r"\s+", " ", chunk)
    chunk = re.sub(r"\s+;", ";", chunk).strip(" ;")
    chunk = re.sub(r"(?:; ){2,}", "; ", chunk)
    for prefix in starts:
        chunk = re.sub(rf"^{re.escape(prefix)}[:\s]*", "", chunk, flags=re.I)
    for marker in (
        " Diagnostic Evaluation",
        " Critically Analyze the Evidence",
        " Guiding Principles",
        " TEXAS CHILDREN",
        " Practice Recommendations",
        " Critical Points of Evidence",
        " Assessment ",
        " Clinical Appearance",
        " Laboratory findings",
        " - Consider referral",
    ):
        cut = chunk.find(marker)
        if cut > 15:
            chunk = chunk[:cut]
    chunk = chunk.strip(" -;:")
    if len(chunk) > limit:
        sentence = chunk.rfind(". ", 0, limit)
        chunk = chunk[: sentence + 1] if sentence > 80 else chunk[:limit].rsplit(" ", 1)[0]
    return chunk.strip()


def load_manifest() -> dict[int, dict]:
    rows = {}
    with (STANDARDS / "manifest.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows[int(row["index"])] = row
    return rows


def system_prompt(entry: dict, inclusion: str, exclusion: str, pdf_rel: str) -> str:
    companions = ", ".join(entry["companions"]) or "none"
    steps = "\n".join(f"- {item}" for item in entry["checkpoints"])
    proposals = "\n".join(f"- {item}" for item in entry["may_propose"])
    campus = entry.get("campus")
    campus_line = f"Campus workflow: {campus}. Do not use the other campus algorithm.\n" if campus else ""
    return (
        f"{PREAMBLE}\n\n"
        f"Agent: {entry['id']}\n"
        f"Standard: {entry['title']}\n"
        f"Bound PDF: {pdf_rel}\n"
        f"{campus_line}"
        f"Job: {entry['mission']}\n\n"
        f"Inclusion: {inclusion}\n"
        f"Exit: {exclusion}\n\n"
        f"Walk these checkpoints, in order, and only as far as the PDF supports:\n{steps}\n\n"
        f"You may propose only:\n{proposals}\n\n"
        f"Companion agents: {companions}.\n"
        f"Default card indicator when the patient is inside the population: {entry['indicator']}.\n"
        f"Epic hook for this draft: {entry['hook']}."
    )


def agent_markdown(agent: dict) -> str:
    also = ", ".join(f"`{hook}`" for hook in agent["epic"]["additionalHooks"]) or "none"
    prefetch = "\n".join(f"- `{key}`: `{value}`" for key, value in agent["epic"]["prefetch"].items())
    steps = "\n".join(f"- {item}" for item in agent["checkpoints"])
    proposals = "\n".join(f"- {item}" for item in agent["mayPropose"])
    companions = ", ".join(f"`{item}`" for item in agent["companions"]) or "none"
    return f"""# {agent['title']}

Draft Epic agent `{agent['id']}`. Clinical review is required before anyone turns it on in Hyperspace. The bound PDF is the clinical source. This file is the integration contract and the instructions, not a second copy of the standard.

## Role

{agent['mission']}

## When Epic calls it

- Primary CDS Hook: `{agent['epic']['hook']}`
- Can also be registered at: {also}
- Setting: {", ".join(agent['settings'])}
- Card indicator when the patient is inside the population: `{agent['epic']['indicatorWhenApplicable']}`
- Suggestions stay unsigned. This service returns no `systemActions`.

## Population

**Inclusion.** {agent['population']['inclusion']}

**Exit.** {agent['population']['exclusion']}

## What it walks

{steps}

## What it may return

{proposals}

## FHIR prefetch

Epic should resolve these before the hook call. `draftOrders` and `selections` arrive in the hook context for `order-select` and `order-sign`; they are not prefetched.

{prefetch}

## Companion agents

{companions}

## System prompt

```text
{agent['systemPrompt']}
```

## Source

- Publisher: Texas Children's Hospital Evidence-Based Outcomes Center
- Local PDF: `{agent['source']['pdf']}`
- Published file: {agent['source']['sourceUrl']}
- Index page: {agent['source']['page']}
"""


def discovery_service(agent: dict) -> dict:
    return {
        "hook": agent["epic"]["hook"],
        "id": agent["id"],
        "title": f"TCH {agent['title']}",
        "description": agent["mission"],
        "usageRequirements": agent["epic"]["usageRequirements"],
        "prefetch": agent["epic"]["prefetch"],
    }


def build() -> None:
    manifest = load_manifest()
    if len(ENTRIES) != 54:
        raise SystemExit(f"expected 54 entries, found {len(ENTRIES)}")
    ids = [entry["id"] for entry in ENTRIES]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate agent id")

    services = []
    index_rows = []
    for entry in ENTRIES:
        row = manifest[entry["n"]]
        entry["title"] = row["title"]
        entry["category"] = row["category"]
        pdf_name = row["filename"]
        pdf_path = STANDARDS / pdf_name
        if not pdf_path.exists():
            raise SystemExit(f"missing pdf {pdf_path}")
        text = pdf_text(pdf_path)
        override = entry.get("population_override") or {}
        inclusion = override.get("inclusion") or section(
            text,
            ["Inclusion Criteria", "Guideline Eligibility Criteria", "Inclusion criteria"],
            ["Exclusion Criteria", "Guideline Exclusion Criteria", "Critical Points", "Background", "Differential"],
        )
        exclusion = override.get("exclusion") or section(
            text,
            ["Exclusion Criteria", "Guideline Exclusion Criteria", "Exclusion criteria"],
            ["Critical Points", "Background", "Differential", "Practice Recommendations", "Begin", "History:"],
        )
        if not inclusion or not exclusion:
            raise SystemExit(f"population missing for {entry['id']}: inc={bool(inclusion)} exc={bool(exclusion)}")
        for hook in [entry["hook"], *entry["also"]]:
            if hook not in HOOKS:
                raise SystemExit(f"unsupported hook {hook} on {entry['id']}")
        if len(entry["summary"]) > 140:
            raise SystemExit(f"summary too long ({len(entry['summary'])}) for {entry['id']}")

        pdf_rel = f"clinical-standards/{pdf_name}"
        prefetch = {key: QUERIES[key] for key in PREFETCH[entry["prefetch"]]}
        agent = {
            "specVersion": "0.1-draft",
            "status": "draft",
            "clinicalReview": "Required before activation in Epic. Not the standard of care.",
            "id": entry["id"],
            "index": entry["n"],
            "title": entry["title"],
            "category": entry["category"],
            "documentType": entry["doc_type"],
            "settings": entry["settings"],
            "mission": entry["mission"],
            "checkpoints": entry["checkpoints"],
            "mayPropose": entry["may_propose"],
            "companions": entry["companions"],
            "cardSummary": entry["summary"],
            "population": {
                "inclusion": inclusion,
                "exclusion": exclusion,
                "source": "catalog-override" if override else "pdf-extract",
            },
            "source": {
                "publisher": "Texas Children's Hospital Evidence-Based Outcomes Center",
                "pdf": pdf_rel,
                "sourceUrl": row["source_url"],
                "originalFilename": row["original_filename"],
                "page": PAGE,
            },
            "epic": {
                "hook": entry["hook"],
                "additionalHooks": entry["also"],
                "indicatorWhenApplicable": entry["indicator"],
                "prefetch": prefetch,
                "usageRequirements": (
                    "Decision support only. The clinician accepts every suggestion in Epic. "
                    "The bound TCH EBOC PDF is the clinical source. Do not enable until clinical review."
                ),
                "suggestionPolicy": "unsigned-fhir-or-education-only",
                "systemActions": False,
                "smartAppContext": {"agentId": entry["id"]},
            },
            "systemPrompt": system_prompt(entry, inclusion, exclusion, pdf_rel),
        }
        folder = AGENTS / "standards" / f"{entry['n']:02d}-{entry['slug']}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "agent.json").write_text(json.dumps(agent, indent=2) + "\n")
        (folder / "AGENT.md").write_text(agent_markdown(agent))
        services.append(discovery_service(agent))
        index_rows.append(
            {
                "index": entry["n"],
                "id": entry["id"],
                "title": entry["title"],
                "hook": entry["hook"],
                "indicator": entry["indicator"],
                "documentType": entry["doc_type"],
                "path": str(folder.relative_to(ROOT)),
            }
        )
        print(f"wrote {entry['n']:02d} {entry['id']}")

    discovery = {
        "services": services,
    }
    (AGENTS / "cds-services.json").write_text(json.dumps(discovery, indent=2) + "\n")
    (AGENTS / "catalog.json").write_text(json.dumps(index_rows, indent=2) + "\n")
    print(f"discovery services: {len(services)}")


if __name__ == "__main__":
    build()
