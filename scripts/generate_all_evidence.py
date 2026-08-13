"""Script to execute discovery, replay, error, and handoff flows to generate full evidence set."""
import os
import sys
import time
import json
import threading
import uvicorn
from playwright.sync_api import sync_playwright

from app.demo_bank.main import app as fastapi_app
from app.demo_bank.models import GLOBAL_FAULT_STATE
from app.surface.playwright_surface import PlaywrightSurface
from app.agent.agent import DiscoveryAgent
from app.replay.engine import ReplayEngine
from app.handoff.manager import HandoffManager
from app.common.observability import EvidenceExporter
from app.artifacts.schema import CapabilityArtifact

def run_server():
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="error")

def main():
    print("=== Generating Complete Evidence Suite ===")
    os.makedirs("evidence", exist_ok=True)
    os.makedirs("artifacts", exist_ok=True)

    # Start Demo Bank server thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Run LLM Discovery
        print("\n[1/4] Running Discovery Flow...", flush=True)
        context = browser.new_context()
        page = context.new_page()
        surface = PlaywrightSurface(page)
        agent = DiscoveryAgent(surface=surface)

        artifact = agent.run_discovery(
            goal="Look up member 12345 and read their current savings balance",
            start_url="http://127.0.0.1:8000/members",
            capability_id="member.savings_balance.lookup"
        )
        context.close()
        print(" -> Discovery evidence generated (discovery.json, discovery.log, discovery.png, artifact.json).")

        # 2. Run Successful Deterministic Replay
        print("\n[2/4] Running Successful Replay Flow...")
        context = browser.new_context()
        page = context.new_page()
        surface = PlaywrightSurface(page)
        engine = ReplayEngine(surface=surface)
        exporter = EvidenceExporter()

        res_success = engine.execute(artifact, input_params={"member_id": "12345"})
        exporter.record_replay_result(res_success, is_error=False, surface=surface)
        context.close()
        print(" -> Replay success evidence generated (replay-success.json).")

        # 3. Run Error Replay (MEMBER_NOT_FOUND)
        print("\n[3/4] Running Error Scenario Replay Flow...")
        context = browser.new_context()
        page = context.new_page()
        surface = PlaywrightSurface(page)
        engine = ReplayEngine(surface=surface)

        res_error = engine.execute(artifact, input_params={"member_id": "99999"})
        exporter.record_replay_result(res_error, is_error=True, surface=surface)
        context.close()
        print(" -> Replay error evidence generated (replay-error.json, replay-error.png).")

        # 4. Run Risky Action Handoff Scenario
        print("\n[4/4] Running Human Handoff Scenario Flow...", flush=True)
        context = browser.new_context()
        page = context.new_page()
        surface = PlaywrightSurface(page)

        # Discovery sub-account trajectory for handoff
        agent_sub = DiscoveryAgent(surface=surface)
        sub_artifact = agent_sub.run_discovery(
            goal="Open a new savings sub-account for member 12345",
            start_url="http://127.0.0.1:8000/members",
            capability_id="member.subaccount.create"
        )

        # Replay sub-account artifact with handoff manager
        handoff_mgr = HandoffManager(auto_approve_in_tests=True)
        engine_sub = ReplayEngine(surface=surface)
        res_handoff = engine_sub.execute(sub_artifact, input_params={"member_id": "12345"}, handoff_manager=handoff_mgr)

        context.close()
        browser.close()

    print("\n=== All Evidence Successfully Generated in /evidence ===")
    print("Files in /evidence:")
    for f in os.listdir("evidence"):
        print(f" - evidence/{f}")

    os._exit(0)

if __name__ == "__main__":
    main()
