# TCH clinical-standard agents for Epic

First draft of one agent for each document on the [Texas Children's clinical standards page](https://www.texaschildrens.org/patients-families/safety-and-outcomes/clinical-standards). There are 54. Two of them are the BRUE parent handouts, not treatment algorithms. The Houston and Austin stroke files are campus workflow agents. The other stroke file is the evidence guideline they both cite.

These agents are not approved for clinical use. Turning one on in Epic requires review by the content owners of that standard. A card from this draft is decision support. It is not the standard of care, and it does not sign an order.

## How Epic calls one

Epic's documented interface for an outside decision-support service is [CDS Hooks](https://cds-hooks.hl7.org/). Epic invokes a registered HTTPS service when a clinician reaches a workflow point, sends the FHIR context, and displays the cards the service returns. Medication and procedure suggestions are unsigned until the clinician accepts them. Epic documents this on [open.epic](https://fhir.epic.com/Documentation?docId=cdshookstutorial).

Each agent is one CDS service:

| Piece | Where it lives |
| --- | --- |
| Discovery document Epic fetches | `cds-services.json` |
| One service definition plus the system prompt | `standards/NN-slug/agent.json` |
| The same contract, readable | `standards/NN-slug/AGENT.md` |
| The clinical source the prompt is bound to | `clinical-standards/*.pdf` |
| Loader that puts the PDF text into a model call | `runtime/knowledge.py` |
| Local wiring server | `runtime/serve.py` |

Hooks used in this draft are ones Epic documents: `patient-view`, `encounter-start`, `order-select`, and `order-sign`. Acute recognition agents use `encounter-start`. Agents that should look at a draft order use `order-select`. Screening, chronic care, and the parent handouts use `patient-view`.

`order-select` and `order-sign` already include `draftOrders` and `selections` in the hook context. Those are not repeated in prefetch.

Prefetch templates use FHIR R4 queries Epic can resolve, with `{{context.patientId}}` and `{{context.encounterId}}`. A TCH Epic analyst still has to confirm each query against the version of Hyperspace in production. A prefetch Epic cannot resolve should be removed before go-live, because a failed prefetch can spoil the hook call.

No agent returns `systemActions`. Nothing in this draft updates the chart by itself.

## What an agent knows

The system prompt allows one clinical source: the PDF for that standard. `runtime/knowledge.py` loads that PDF, with page markers, into the model request together with the Epic hook payload. Doses, thresholds, and time windows have to come from a page in that PDF. If the chart is outside the inclusion population, or an exit criterion is present, the agent returns no treatment card.

`build.py` stores a short inclusion and exit statement so a reviewer can see who the agent is for. Where the PDF states those criteria in a clean block, the text is extracted. Where the PDF is a flowchart and the criteria are inside the drawing, the catalog holds a short population statement instead. Either way, the PDF remains the source the model reads.

Checkpoint lists in each `AGENT.md` are the review surface. They describe the job. They are not a second protocol, and they do not contain doses.

## Run the draft endpoint

From the repository root, after the agent files exist:

```bash
python3 agents/build.py
python3 agents/runtime/serve.py --insecure-dev --port 8787
```

Then:

```bash
curl -s http://127.0.0.1:8787/cds-services | python3 -m json.tool | head
curl -s -X POST http://127.0.0.1:8787/cds-services/tch-dka \
  -H 'Content-Type: application/json' \
  -d '{"hook":"encounter-start","hookInstance":"demo","context":{"patientId":"example"}}'
```

The server listens only with `--insecure-dev`. It does not verify the JWT Epic attaches to a real hook call. Production needs TLS and Epic's JWKS. The card this server returns is a wiring card: it names the standard and links the published PDF. It does not recommend a dose. Treatment cards come from a model call built by `runtime/knowledge.py`, after review.

## Before a pilot in Epic

1. The content owner for that standard reads `AGENT.md` against the current PDF.
2. An Epic analyst registers the CDS Hooks base URL and confirms the hook and prefetch on the TCH Epic version.
3. The first pilot returns cards only, with suggestions empty, in one department.
4. Unsigned orders are mapped to real Epic orderables only after that review. A suggestion names the intent. It does not yet carry a MedicationRequest.
5. Accept, dismiss, and override are logged against the clinician and the agent id.

A SMART on FHIR app can be launched from a card later. Each agent already carries `smartAppContext.agentId` for that launch. This draft does not include the app.
