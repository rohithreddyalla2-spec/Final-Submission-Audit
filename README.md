# Computer-Use Automation Take-Home — Vertical Slice

A clean, production-grade end-to-end vertical slice of a computer-use automation system. The system discovers workflows on a live UI using an LLM, compiles them into structured/versioned capability artifacts, replays them deterministically without LLM decision-making, handles business outcomes & errors, enforces safety guardrails, and supports human escalation/handoff within the same live browser session.

---

## 1. Overview

The automation lifecycle follows a 7-stage architectural pipeline:

```text
Natural-language goal
        ↓
LLM-driven discovery against a live UI
        ↓
Successful execution
        ↓
Structured/versioned capability artifact
        ↓
Deterministic replay WITHOUT LLM decision-making
        ↓
Structured outputs / business outcomes / failures
        ↓
Human escalation when automation cannot safely continue
```

---

## 2. Requirements

* **Python 3.12+**
* **Playwright** (Chromium)
* **FastAPI** & **Uvicorn**
* **Pydantic v2**
* **OpenAI API** (or fallback algorithmic discovery engine when `OPENAI_API_KEY` is omitted)
* **pytest**

---

## 3. Setup

```bash
# 1. Create and activate Python 3.12 virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -e .

# 3. Install Playwright Chromium browser
playwright install chromium
```

---

## 4. Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Example `.env` configuration:

```env
DEMO_BANK_HOST=127.0.0.1
DEMO_BANK_PORT=8000
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
HEADLESS=true
```

*(Note: If `OPENAI_API_KEY` is not provided, the Discovery Agent seamlessly uses a rule-based fallback discovery engine to inspect the DOM and complete workflows deterministically.)*

---

## 5. Run Demo App

Start the local fake banking back-office UI server:

```bash
python -m app.demo_bank
```

Access the application in your browser at [http://127.0.0.1:8000/members](http://127.0.0.1:8000/members).

---

## 6. Run Discovery

Run LLM-driven discovery against the live application:

```bash
python -m app.agent --goal "Look up member 12345 and read their current savings balance"
```

This discovers the workflow, interacts with the live UI, records the trajectory, and compiles it into a Capability Artifact.

---

## 7. Inspect Artifact

The compiled capability artifact is stored under `artifacts/`:

```bash
cat artifacts/member_savings_balance_lookup.json
```

The artifact contains:
- `schema_version`: "1.0"
- `capability_id`: "member.savings_balance.lookup"
- `inputs`: Typed input specifications (`member_id`)
- `outputs`: Typed output specifications (`savings_balance`)
- `steps`: Robust multi-tiered locator steps
- `checkpoint`: Success verification condition

---

## 8. Run Deterministic Replay

Execute the saved capability artifact **WITHOUT any LLM decision-making during replay**:

```bash
python -m app.replay --artifact artifacts/member_savings_balance_lookup.json --member-id 12345
```

Output:
```json
{
  "status": "success",
  "capability_id": "member.savings_balance.lookup",
  "outputs": {
    "savings_balance": 12450.32
  },
  "execution_time_ms": 464.3
}
```

---

## 9. Run Failure / Error Scenario

Demonstrate structured business outcomes (`MEMBER_NOT_FOUND`) for non-existent member IDs:

```bash
python -m app.replay --artifact artifacts/member_savings_balance_lookup.json --member-id 99999
```

Output:
```json
{
  "status": "business_outcome",
  "code": "MEMBER_NOT_FOUND",
  "step_id": "step_1_nav",
  "capability_id": "member.savings_balance.lookup",
  "expected": "Member details page",
  "observed": "Member not found in database"
}
```

---

## 10. Run Tests

Execute the complete pytest suite covering artifact schemas, safety guardrails, fault injection replay states, and human-in-the-loop handoff:

```bash
pytest -v
```

---

## 11. Architecture

The codebase is structured modularly into decoupled layers:

* `app/demo_bank`: FastAPI back-office app serving HTML forms, tables, labels, imperfect markup, and fault injection endpoints.
* `app/surface`: `Surface` protocol abstraction and `PlaywrightSurface` implementation with a 5-tier robust locator priority engine (Role+Name -> Label -> Semantic Attribute -> Text -> CSS fallback).
* `app/artifacts`: Pydantic schema models and `compiler` for trajectory-to-artifact compilation.
* `app/replay`: Deterministic Replay Engine executing artifacts step-by-step without LLM calls.
* `app/safety`: Safety Policy layer enforcing domain allowlists, action allowlists, risky action flags, and PII redaction.
* `app/handoff`: Handoff Manager pausing execution on risky steps, maintaining the **same live browser session**, accepting human control, and resuming execution.
* `app/agent`: LLM Discovery Agent with observe-decide-safety-act loop.
* `app/common`: Observability and evidence export utilities.

---

## 12. Evidence Directory

The `/evidence` folder contains generated artifacts and proof of execution:

* `evidence/discovery.json`: Trajectory log of the LLM discovery run.
* `evidence/discovery.log`: Structured text log of discovery steps.
* `evidence/discovery.png`: Full-page screenshot captured after discovery.
* `evidence/artifact.json`: Validated Capability Artifact output.
* `evidence/replay-success.json`: Structured outcome of successful deterministic replay.
* `evidence/replay-error.json`: Structured result of error replay (`MEMBER_NOT_FOUND`).
* `evidence/replay-error.png`: Screenshot captured on replay failure/outcome.
* `evidence/handoff.json`: Record of same-session human escalation, pause, and resumption.
