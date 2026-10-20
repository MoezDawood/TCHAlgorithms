# TCH Algorithms

Draft clinical decision-support agents for the [Texas Children's clinical standards](https://www.texaschildrens.org/patients-families/safety-and-outcomes/clinical-standards), shaped so Epic can call them.

Each published standard has one agent. Epic reaches an agent through [CDS Hooks](https://cds-hooks.hl7.org/): a clinician opens a chart or selects an order, Epic sends the FHIR context, and the agent returns a card. Suggestions stay unsigned until the clinician accepts them. Nothing in this draft writes to the chart on its own.

These agents are not approved for clinical use. A card is decision support. It is not the standard of care. The content owner for a standard has to review that agent before it is turned on in Epic.

## What is in this repository

| Path | Contents |
| --- | --- |
| `agents/standards/` | One folder per standard. `AGENT.md` is the readable contract. `agent.json` is the CDS Hooks service, the population, and the system prompt. |
| `agents/cds-services.json` | Discovery document for all 54 services. |
| `agents/catalog.json` | Index of agent id, hook, and indicator. |
| `clinical-standards/manifest.csv` | Title, category, and the published URL for each source document. |
| `agents/README.md` | How the Epic hook, prefetch, and local wiring server fit together. |

There are 54 agents. Two are the Brief Resolved Unexplained Event parent handouts. The Houston and Austin stroke files are campus workflow agents. The stroke guideline agent cites the evidence and sends the first day of care to the campus algorithm.

## Source documents

The original PDFs are not in this repository. `clinical-standards/manifest.csv` lists the file name and the Texas Children's URL for each one. To run an agent against its source, download the PDF into `clinical-standards/` using the filename in that manifest. `agents/runtime/knowledge.py` reads that local file and passes the text, with page markers, into the model request.

The system prompt allows one clinical source: that PDF. Doses, thresholds, and time windows have to be quoted from a page in it. If the chart is outside the inclusion population, or an exit criterion is present, the agent returns no treatment card.

## Hooks

| Workflow | CDS Hook | Examples |
| --- | --- | --- |
| Acute recognition | `encounter-start` | DKA, septic shock, stroke, status epilepticus |
| Draft-order check | `order-select` | Transfusion, ketamine, sedation, high-flow nasal cannula |
| Screening, chronic care, handouts | `patient-view` | ADHD, autism, chronic asthma, BRUE handouts |

`order-sign` is available for a second registration on the order-check agents. Prefetch templates are FHIR R4. A TCH Epic analyst still has to confirm each query on the Hyperspace version in production.

## Run the draft endpoint

```bash
python3 agents/build.py
python3 agents/runtime/serve.py --insecure-dev --port 8787
```

`GET /cds-services` returns the 54 services. `POST /cds-services/{id}` returns a wiring card that links the published PDF and includes no orders. The server does not verify Epic's JWT. Production needs TLS and Epic's JWKS. Details are in `agents/README.md`.
