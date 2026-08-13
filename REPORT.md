# Architecture

The system is structured as a decoupled 7-stage computer-use automation pipeline:

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

### Decoupled Component Boundaries
1. **Surface Layer (`app/surface`)**: Abstract `Surface` protocol decoupled from Playwright. `PlaywrightSurface` implements browser interactions, while future surface drivers (Desktop GUI, Accessibility API, Vision/Coordinate adapter) can fulfill the same interface without modifying the replay engine or discovery agent.
2. **Safety Layer (`app/safety`)**: Independent policy engine verifying domain allowlists, action permissions, risky action classification, and recursive PII/credential redaction.
3. **Artifact Compiler (`app/artifacts`)**: Takes raw LLM trajectories, strips model reasoning/scratchpad text, parameterizes inputs/outputs, and produces serializable, versioned `CapabilityArtifact` models.
4. **Deterministic Replay Engine (`app/replay`)**: Executes compiled artifacts step-by-step using strict precondition/postcondition checks. **Replay uses zero LLM calls for decision-making.**
5. **Handoff Manager (`app/handoff`)**: Coordinates escalation when risky actions or unrecoverable conditions occur, maintaining the **same live Playwright browser context** for human takeover and seamless resumption.

---

# Artifact schema

The `CapabilityArtifact` model (`app/artifacts/schema.py`) defines a typed, versioned, machine-readable contract representing reusable UI capabilities:

```json
{
  "schema_version": "1.0",
  "capability_id": "member.savings_balance.lookup",
  "description": "Look up a member's current savings balance",
  "target": {
    "surface": "browser",
    "application": "demo-bank"
  },
  "inputs": {
    "member_id": {
      "type": "string",
      "required": true,
      "default": "12345"
    }
  },
  "outputs": {
    "savings_balance": {
      "type": "number",
      "description": "Current savings account balance"
    }
  },
  "steps": [
    {
      "step_id": "step_1_navigate",
      "action": "navigate",
      "url": "http://127.0.0.1:8000/members"
    },
    {
      "step_id": "step_2_fill_search",
      "action": "fill",
      "locator": {
        "role": "textbox",
        "label": "Search by Member ID",
        "css_fallback": "#search_member_id_input"
      },
      "input_param": "member_id"
    }
  ],
  "checkpoint": {
    "type": "text_contains",
    "expected_value": "Member Account Details"
  }
}
```

### Multi-Tiered Robust Locators
To prevent brittleness on imperfect DOMs without test IDs, locators follow a strict 5-level priority strategy:
1. **Accessibility Role + Accessible Name**: ARIA role + button/link text (e.g. `role="button"`, `name="Search Member"`).
2. **Label Text**: Form field labels (`label="Search by Member ID"`).
3. **Stable Semantic Attribute**: HTML attributes (`id`, `name`, `data-test`).
4. **Visible Inner Text**: Exact or partial text match.
5. **CSS Selector Fallback**: CSS path fallback.

---

# Determinism & error handling

### Replay Determinism
Replay runs directly against the structured capability artifact. No LLM prompts, reasoning, or probabilistic decision-making occur during replay. Every step performs:
`locate target → verify target state → perform action → verify expected result → check page fault states`.

### Error Taxonomy
Failures are categorized into explicit states rather than unhandled Python exceptions:

1. **Business Outcome (`BUSINESS_OUTCOME`)**:
   - `MEMBER_NOT_FOUND`: Member ID does not exist in banking database (e.g. member `99999`). This is a valid domain outcome, not a system crash.
   - `VALIDATION_ERROR`: Form submission failed application validation rules.
2. **Recoverable Condition (`RECOVERABLE_FAILURE`)**:
   - `TRANSIENT_LOAD_FAILURE`: Page delay or temporary 503 load spike.
   - `UNEXPECTED_DIALOG`: Interstitial maintenance popup overlay detected. Engine can attempt dismissal or retry.
3. **Hard Failure (`HARD_FAILURE`)**:
   - `SESSION_TIMEOUT`: Session expired or redirected to authentication.
   - `APPLICATION_ERROR`: HTTP 500 internal server error.
   - `LOCATOR_FAILURE`: Target element missing or unresolvable.
   - `SAFETY_POLICY_VIOLATION`: Action rejected by policy engine.

---

# Heterogeneity & multi-tenant

### Cross-Tenant & Variant Support
* **Parameterization**: Artifacts specify inputs using Jinja templates (e.g., `{{member_id}}`, `{{subaccount_name}}`). The same capability artifact can execute across multiple tenants, environments, or user accounts by passing distinct input dictionaries.
* **Schema Versioning**: Every artifact carries a `schema_version: "1.0"` tag. Backward-compatible migrations can be implemented via schema upgraders.
* **Surface Decoupling**: Target applications specify `target.surface = "browser"` or `target.application = "demo-bank"`, allowing tenant-specific surface adapters (e.g., legacy Internet Explorer wrappers, Citrix desktop automation, or direct HTTP API backends) to be swapped without changing replay logic.

---

# Escalation & handoff

### Same-Session Human Takeover
When automation encounters a risky action (e.g. creating a financial sub-account) or an unrecoverable failure, `HandoffManager` pauses execution:

```text
RUNNING → PAUSED → HUMAN_CONTROL → RESUMED → RUNNING
```

1. **Pause**: Automation freezes. Full state, screenshot (`evidence/handoff.png`), and step context are exported to `evidence/handoff.json`.
2. **Preserve Session**: The live Playwright `BrowserContext` and `Page` remain open. No second browser instance is launched.
3. **Human Control**: The operator reviews the live screen/prompt, performs manual actions or clicks approve, and signals resumption.
4. **Resume**: Automation resumes execution on the exact same browser page where it paused.

---

# Safety

### Configurable Policy Layer (`app/safety/policy.py`)
1. **Domain Allowlist**: Restricts browser navigation exclusively to approved hostnames (`localhost`, `127.0.0.1`). External domain navigation is blocked immediately.
2. **Action Allowlist**: Restricts executable surface methods to safe primitives (`navigate`, `click`, `fill`, `read`, `wait`). Arbitrary script downloads or command execution are prohibited.
3. **Risky Action Classification**: Detects keywords (`create`, `submit`, `withdraw`, `pay`) in actions or element texts and enforces human operator approval before execution.
4. **PII & Credential Redaction**: Automatically redacts passwords, tokens, SSNs, and credit card numbers from evidence logs and JSON outputs.

---

# Cuts

### Deliberate Omissions
* **Infrastructure**: Omitted Kubernetes, Redis, message queues, Docker, and distributed databases in favor of standard Python stdlib and lightweight JSON files.
* **Real Financial Systems**: Built an in-memory FastAPI back-office bank server to avoid real financial risk and credential dependency.
* **Real-time Co-browsing WebRTC Stream**: Implemented same-session browser context preservation with operator CLI/API approval rather than a complex canvas-streaming UI.

### Next Steps / Future Enhancements
1. **Desktop / Accessibility Driver**: Implement `AccessibilitySurface` using Windows UI Automation API.
2. **LLM Recovery Step**: Implement single-step LLM-assisted locator recovery when a selector breaks during replay.
3. **Visual Regression Verification**: Integrate screenshot diffing during checkpoint evaluation.
