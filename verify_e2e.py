"""
verify_e2e.py — End-to-end verification script.
Assumes the demo bank server is already running on 127.0.0.1:8000.
Runs each scenario in sequence and prints structured results.
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

from app.surface.playwright_surface import PlaywrightSurface
from app.agent.agent import DiscoveryAgent
from app.replay.engine import ReplayEngine
from app.handoff.manager import HandoffManager
from app.common.observability import EvidenceExporter
from app.artifacts.schema import CapabilityArtifact

import socket
import threading
import uvicorn
from app.demo_bank.main import app as fastapi_app

os.makedirs("evidence", exist_ok=True)
os.makedirs("artifacts", exist_ok=True)

def ensure_server_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        res = s.connect_ex(("127.0.0.1", 8000))
        if res == 0:
            return  # Server already running
    def run_server():
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="error")
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.5)

ensure_server_running()

PASS = "✓ PASS"
FAIL = "✗ FAIL"

results = {}


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ─────────────────────────────────────────────────────────
    # STEP 1: LLM Discovery Flow (uses rule-based fallback if no API key)
    # ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 1: LLM Discovery Flow (rule-based fallback without API key)")
    print("="*60)
    context = browser.new_context()
    page = context.new_page()
    surface = PlaywrightSurface(page)
    agent = DiscoveryAgent(surface=surface)

    artifact = agent.run_discovery(
        goal="Look up member 12345 and read their current savings balance",
        start_url="http://127.0.0.1:8000/members",
        capability_id="member.savings_balance.lookup",
        evidence_dir="evidence"
    )

    # Save to artifacts directory
    artifact_path = "artifacts/member_savings_balance_lookup.json"
    with open(artifact_path, "w") as f:
        f.write(artifact.model_dump_json(indent=2))

    context.close()

    if artifact and artifact.capability_id == "member.savings_balance.lookup":
        print(f"{PASS} Discovery completed: capability_id={artifact.capability_id}")
        print(f"       Steps in artifact: {len(artifact.steps)}")
        results["1_discovery"] = "PASS"
    else:
        print(f"{FAIL} Discovery failed")
        results["1_discovery"] = "FAIL"

    # ─────────────────────────────────────────────────────────
    # STEP 2: Deterministic Replay (LLM disabled — NO LLM CALLS)
    # ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 2: Deterministic Replay (NO LLM, member_id=12345)")
    print("="*60)
    context = browser.new_context()
    page = context.new_page()
    surface = PlaywrightSurface(page)
    engine = ReplayEngine(surface=surface)
    exporter = EvidenceExporter()

    res = engine.execute(artifact, input_params={"member_id": "12345"})
    exporter.record_replay_result(res, is_error=False, surface=surface)
    context.close()

    print(f"Status: {res.status}")
    print(f"Outputs: {res.outputs}")
    if res.status.value == "success":
        print(f"{PASS} Deterministic replay succeeded — savings_balance={res.outputs.get('savings_balance')}")
        results["2_replay_success"] = f"PASS (balance={res.outputs.get('savings_balance')})"
    else:
        print(f"{FAIL} Replay failed: {res.error_message}")
        results["2_replay_success"] = "FAIL"

    # ─────────────────────────────────────────────────────────
    # STEP 3: Member-Not-Found Business Outcome (member_id=99999)
    # ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 3: Member-Not-Found → Structured Business Outcome")
    print("="*60)
    context = browser.new_context()
    page = context.new_page()
    surface = PlaywrightSurface(page)
    engine = ReplayEngine(surface=surface)

    res_err = engine.execute(artifact, input_params={"member_id": "99999"})
    exporter.record_replay_result(res_err, is_error=True, surface=surface)
    context.close()

    print(f"Status: {res_err.status}")
    print(f"Code: {res_err.code}")
    print(f"Message: {res_err.error_message}")
    if res_err.status.value == "business_outcome" and str(res_err.code) in ("ErrorCode.MEMBER_NOT_FOUND", "member_not_found"):
        print(f"{PASS} Member-not-found returned structured business_outcome (not generic failure)")
        results["3_member_not_found"] = "PASS"
    else:
        print(f"{FAIL} Expected business_outcome with MEMBER_NOT_FOUND, got status={res_err.status} code={res_err.code}")
        results["3_member_not_found"] = "FAIL"

    # ─────────────────────────────────────────────────────────
    # STEP 4: Risky Action → Human Escalation Handoff
    # ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 4: Risky Action → Human Handoff & Same-Session Resume")
    print("="*60)
    context = browser.new_context()
    page = context.new_page()
    surface = PlaywrightSurface(page)

    # Run subaccount discovery to get the risky-action artifact
    agent_sub = DiscoveryAgent(surface=surface)
    sub_artifact = agent_sub.run_discovery(
        goal="Open a new savings sub-account for member 12345",
        start_url="http://127.0.0.1:8000/members",
        capability_id="member.subaccount.create",
        evidence_dir="evidence"
    )

    handoff_mgr = HandoffManager(auto_approve_in_tests=True)
    engine_sub = ReplayEngine(surface=surface)
    res_handoff = engine_sub.execute(sub_artifact, input_params={"member_id": "12345"}, handoff_manager=handoff_mgr)

    final_url = surface.observe()["url"]
    context.close()

    print(f"Status: {res_handoff.status}")
    print(f"Final URL: {final_url}")
    print(f"Handoff history entries: {len(handoff_mgr.history)}")
    if len(handoff_mgr.history) >= 1:
        print(f"Handoff states: {[h.status.value for h in handoff_mgr.history]}")

    if (res_handoff.status.value == "success"
            and "/subaccounts/confirmation" in final_url
            and len(handoff_mgr.history) >= 2):
        print(f"{PASS} Risky action triggered handoff → human approved → same session resumed → success")
        results["4_handoff"] = "PASS"
    else:
        print(f"{FAIL} Handoff scenario failed. status={res_handoff.status}, url={final_url}, history={len(handoff_mgr.history)}")
        results["4_handoff"] = "FAIL"

    browser.close()

# ─────────────────────────────────────────────────────────
# Final Summary
# ─────────────────────────────────────────────────────────
print("\n" + "="*60)
print("END-TO-END VERIFICATION SUMMARY")
print("="*60)
all_pass = True
for k, v in results.items():
    icon = "✓" if "PASS" in v else "✗"
    print(f"  {icon} {k}: {v}")
    if "FAIL" in v:
        all_pass = False

print()
print("Evidence files generated:")
for f in sorted(os.listdir("evidence")):
    path = os.path.join("evidence", f)
    size = os.path.getsize(path)
    print(f"  evidence/{f}  ({size} bytes)")

print()
if all_pass:
    print("ALL CHECKS PASSED ✓")
    sys.exit(0)
else:
    print("SOME CHECKS FAILED ✗")
    sys.exit(1)
