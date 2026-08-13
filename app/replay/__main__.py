"""CLI entrypoint for Deterministic Replay Engine."""
import os
import sys
import json
import argparse
from playwright.sync_api import sync_playwright
from app.surface.playwright_surface import PlaywrightSurface
from app.artifacts.schema import CapabilityArtifact
from app.replay.engine import ReplayEngine
from app.handoff.manager import HandoffManager
from app.common.observability import EvidenceExporter
from app.replay.result import ReplayStatus

def main():
    parser = argparse.ArgumentParser(description="Run Deterministic Replay Engine on Capability Artifact.")
    parser.add_argument("--artifact", type=str, required=True, help="Path to Capability Artifact JSON file.")
    parser.add_argument("--member-id", type=str, default="12345", help="Target Member ID input parameter.")
    parser.add_argument("--subaccount-name", type=str, default="Vacation Fund", help="Subaccount custom label parameter.")
    parser.add_argument("--initial-deposit", type=float, default=500.00, help="Subaccount initial deposit amount.")
    parser.add_argument("--auto-approve-handoff", action="store_true", default=False, help="Auto-approve risky action handoff prompt.")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode.")
    args = parser.parse_args()

    if not os.path.exists(args.artifact):
        print(f"Error: Artifact file not found at '{args.artifact}'")
        sys.exit(1)

    with open(args.artifact, "r", encoding="utf-8") as f:
        artifact_json = json.load(f)
    artifact = CapabilityArtifact.model_validate(artifact_json)

    input_params = {
        "member_id": args.member_id,
        "subaccount_name": args.subaccount_name,
        "initial_deposit": args.initial_deposit
    }

    print(f"=== Starting Deterministic Replay (NO LLM DECISION-MAKING) ===")
    print(f"Capability ID: {artifact.capability_id}")
    print(f"Inputs: {input_params}\n")

    exporter = EvidenceExporter()
    handoff_mgr = HandoffManager(auto_approve_in_tests=args.auto_approve_handoff)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        surface = PlaywrightSurface(page)
        engine = ReplayEngine(surface=surface)

        result = engine.execute(
            artifact=artifact,
            input_params=input_params,
            handoff_manager=handoff_mgr
        )

        is_error = result.status != ReplayStatus.SUCCESS
        evidence_path = exporter.record_replay_result(result, is_error=is_error, surface=surface)

        print("=== Deterministic Replay Result ===")
        print(json.dumps(result.model_dump(), indent=2))
        print(f"\nEvidence recorded to: {evidence_path}")

        browser.close()

if __name__ == "__main__":
    main()
