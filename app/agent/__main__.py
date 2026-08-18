"""CLI entrypoint for LLM Discovery Agent."""
import argparse
from playwright.sync_api import sync_playwright
from app.surface.playwright_surface import PlaywrightSurface
from app.agent.agent import DiscoveryAgent


def main():
    """Execute LLM Discovery Agent CLI."""
    parser = argparse.ArgumentParser(
        description="Run LLM Discovery Agent against live UI."
    )
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="Natural language goal for UI discovery.",
    )
    parser.add_argument(
        "--start-url",
        type=str,
        default="http://127.0.0.1:8000/members",
        help="Start URL.",
    )
    parser.add_argument(
        "--capability-id",
        type=str,
        default="member.savings_balance.lookup",
        help="Capability ID.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode.",
    )
    args = parser.parse_args()

    print("=== Starting LLM Discovery Agent ===")
    print(f"Goal: {args.goal}")
    print(f"Start URL: {args.start_url}")
    print(f"Capability ID: {args.capability_id}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        surface = PlaywrightSurface(page)
        agent = DiscoveryAgent(surface=surface)

        agent.run_discovery(
            goal=args.goal,
            start_url=args.start_url,
            capability_id=args.capability_id,
        )

        print("\n=== LLM Discovery Completed Successfully ===")
        artifact_filename = args.capability_id.replace(".", "_")
        print(f"Compiled capability artifact saved to: artifacts/{artifact_filename}.json")
        print(
            "Evidence exported to: evidence/discovery.json, "
            "discovery.log, discovery.png, artifact.json"
        )

        browser.close()


if __name__ == "__main__":
    main()
