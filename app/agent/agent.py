"""LLM Discovery Agent executing Observe -> Decide -> Safety Check -> Act loop."""
import os
import json
import time
from typing import Dict, Any, List, Optional
import openai
from app.surface.base import Surface
from app.surface.locator import LocatorSpec
from app.safety.policy import SafetyPolicy
from app.artifacts.schema import CapabilityArtifact, InputParamDef, OutputParamDef, Checkpoint, CheckpointType
from app.artifacts.compiler import compile_trajectory_to_artifact
from app.agent.prompts import DISCOVERY_SYSTEM_PROMPT

class DiscoveryAgent:
    """Agent that performs live UI discovery and compiles the trajectory into a capability artifact."""

    def __init__(
        self,
        surface: Surface,
        safety_policy: Optional[SafetyPolicy] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o"
    ):
        self.surface = surface
        self.policy = safety_policy or SafetyPolicy()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", model)
        self.openai_client = openai.OpenAI(api_key=self.api_key) if self.api_key else None

    def _decide_with_llm(self, goal: str, obs: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Make genuine LLM decision call using OpenAI API."""
        messages = [
            {"role": "system", "content": DISCOVERY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "goal": goal,
                    "current_state": obs,
                    "action_history": history
                }, indent=2)
            }
        ]
        
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _decide_rule_based_fallback(self, goal: str, obs: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rule-based fallback planner used when OPENAI_API_KEY is not set.
        Inspects DOM elements to complete standard bank workflows deterministically.
        """
        url = obs.get("url", "")
        elems = obs.get("interactive_elements", [])
        snippet = obs.get("visible_text_snippet", "")
        step_count = len(history)

        goal_lower = goal.lower()

        # Workflow A: Member savings balance lookup
        if "lookup" in goal_lower or "savings balance" in goal_lower:
            if "/login" in url or "operator login" in snippet.lower():
                return {
                    "action": "fill",
                    "target": {"role": "textbox", "label": "Operator Username", "css_fallback": "#username_input"},
                    "value": "operator",
                    "input_param": "username",
                    "reason": "Enter operator login username"
                }

            if step_count > 0 and history[-1].get("action") == "fill" and history[-1].get("target", {}).get("css_fallback") == "#username_input":
                return {
                    "action": "click",
                    "target": {"role": "button", "name": "Sign In to Workstation", "css_fallback": "#btn-login-submit"},
                    "reason": "Submit login form"
                }

            if "/members" in url and "/members/" not in url:
                has_filled = any(h.get("action") == "fill" for h in history)
                has_searched = any(h.get("action") == "click" and h.get("target", {}).get("css_fallback") == "#btn-search-member" for h in history)

                if not has_filled:
                    return {
                        "action": "fill",
                        "target": {"role": "textbox", "label": "Search by Member ID", "css_fallback": "#search_member_id_input"},
                        "value": "{{member_id}}",
                        "input_param": "member_id",
                        "reason": "Enter Member ID to search"
                    }
                elif not has_searched:
                    return {
                        "action": "click",
                        "target": {"role": "button", "name": "Search Member", "css_fallback": "#btn-search-member"},
                        "reason": "Submit member search query"
                    }
                else:
                    # Use accessible name rather than hardcoded ID so any member_id resolves
                    return {
                        "action": "click",
                        "target": {"role": "link", "name": "View Details & Accounts", "text": "View Details"},
                        "reason": "View member details page"
                    }

            if "/members/" in url:
                # On details page, read savings balance
                if not any(h.get("action") == "read" for h in history):
                    return {
                        "action": "read",
                        "target": {"semantic_attr": {"id": "val-savings-balance"}, "css_fallback": "#val-savings-balance"},
                        "output_param": "savings_balance",
                        "reason": "Read member primary savings balance"
                    }
                else:
                    return {
                        "action": "finish",
                        "checkpoint": {
                            "type": "text_contains",
                            "expected_value": "Member Account Details"
                        },
                        "reason": "Savings balance successfully read"
                    }

        # Workflow B: Open sub-account
        if "sub-account" in goal_lower or "subaccount" in goal_lower:
            if "/login" in url or "operator login" in snippet.lower():
                return {
                    "action": "fill",
                    "target": {"role": "textbox", "label": "Operator Username", "css_fallback": "#username_input"},
                    "value": "operator",
                    "reason": "Enter operator login"
                }

            if step_count > 0 and history[-1].get("target", {}).get("css_fallback") == "#username_input":
                return {
                    "action": "click",
                    "target": {"role": "button", "name": "Sign In to Workstation", "css_fallback": "#btn-login-submit"},
                    "reason": "Submit login"
                }

            if "/members" in url and "/members/" not in url:
                has_filled = any(h.get("action") == "fill" for h in history)
                has_searched = any(h.get("action") == "click" and (h.get("target") or {}).get("css_fallback") == "#btn-search-member" for h in history)
                
                if not has_filled:
                    return {
                        "action": "fill",
                        "target": {"role": "textbox", "label": "Search by Member ID", "css_fallback": "#search_member_id_input"},
                        "value": "{{member_id}}",
                        "input_param": "member_id",
                        "reason": "Search member ID"
                    }
                elif not has_searched:
                    return {
                        "action": "click",
                        "target": {"role": "button", "name": "Search Member", "css_fallback": "#btn-search-member"},
                        "reason": "Submit search"
                    }
                else:
                    return {
                        "action": "click",
                        "target": {"role": "link", "name": "View Details & Accounts", "text": "View Details"},
                        "reason": "View member details page"
                    }

            if "/members/" in url and "/subaccounts" not in url:
                return {
                    "action": "click",
                    "target": {"role": "link", "name": "Open New Sub-Account", "css_fallback": "#btn-open-new-subaccount"},
                    "reason": "Click open sub-account button"
                }

            if "/subaccounts/new" in url:
                if not any(h.get("action") == "fill" and (h.get("target") or {}).get("css_fallback") == "#subaccount_name_input" for h in history):
                    return {
                        "action": "fill",
                        "target": {"role": "textbox", "label": "Sub-Account Label / Custom Name", "css_fallback": "#subaccount_name_input"},
                        "value": "Secondary Savings",
                        "input_param": "subaccount_name",
                        "reason": "Enter subaccount custom label"
                    }
                else:
                    return {
                        "action": "click",
                        "target": {"role": "button", "name": "Submit & Create Sub-Account", "css_fallback": "#btn-submit-create-subaccount"},
                        "is_risky": True,
                        "reason": "Submit sub-account creation form (Risky action)"
                    }

            if "/subaccounts/confirmation" in url:
                return {
                    "action": "finish",
                    "checkpoint": {
                        "type": "text_contains",
                        "expected_value": "Sub-Account Opened Successfully!"
                    },
                    "reason": "Sub-account confirmation screen reached"
                }

        # Default fallback navigate
        return {
            "action": "navigate",
            "url": "http://127.0.0.1:8000/members",
            "reason": "Initial navigation"
        }

    def run_discovery(
        self,
        goal: str,
        start_url: str = "http://127.0.0.1:8000/members",
        capability_id: str = "member.savings_balance.lookup",
        max_steps: int = 15,
        evidence_dir: str = "evidence"
    ) -> CapabilityArtifact:
        """
        Execute discovery loop: Observe -> Decide -> Safety Check -> Act -> Observe.
        """
        os.makedirs(evidence_dir, exist_ok=True)
        trajectory: List[Dict[str, Any]] = []
        log_lines: List[str] = [f"=== Starting LLM Discovery for Goal: '{goal}' ==="]

        # Initial Navigation — record as step 0 in trajectory
        log_lines.append(f"Navigating to start URL: {start_url}")
        self.surface.navigate(start_url)
        time.sleep(0.5)
        trajectory.append({
            "action": "navigate",
            "url": start_url,
            "target": {},
            "value": None,
            "input_param": None,
            "output_param": None,
            "is_risky": False,
            "description": f"Navigate to workflow start: {start_url}"
        })

        step_idx = 0
        final_checkpoint = Checkpoint(
            type=CheckpointType.TEXT_CONTAINS,
            expected_value="Member Account Details"
        )

        while step_idx < max_steps:
            step_idx += 1
            obs = self.surface.observe()

            # Decide step via LLM or rule-based fallback
            if self.openai_client:
                log_lines.append(f"Step {step_idx}: Requesting LLM decision...")
                decision = self._decide_with_llm(goal, obs, trajectory)
            else:
                log_lines.append(f"Step {step_idx}: OPENAI_API_KEY absent. Using rule-based fallback decision engine...")
                decision = self._decide_rule_based_fallback(goal, obs, trajectory)

            action_str = decision.get("action", "").lower()
            log_lines.append(f"Decision: {json.dumps(decision)}")

            if action_str == "finish":
                if decision.get("checkpoint"):
                    cp_dict = decision["checkpoint"]
                    final_checkpoint = Checkpoint(
                        type=CheckpointType(cp_dict.get("type", "text_contains")),
                        expected_value=cp_dict.get("expected_value")
                    )
                log_lines.append("Goal achieved. Finishing discovery loop.")
                break

            # Safety Policy Check
            target_dict = decision.get("target") or {}
            loc_spec = LocatorSpec(**target_dict) if target_dict else None
            policy_dec = self.policy.evaluate_action(
                action=action_str,
                url=decision.get("url"),
                locator=loc_spec,
                value=decision.get("value"),
                description=decision.get("reason")
            )

            if not policy_dec.allowed:
                log_lines.append(f"Safety Violation! {policy_dec.reason}")
                raise PermissionError(f"Safety Policy blocked action: {policy_dec.reason}")

            # Record step in trajectory
            step_record = {
                "action": action_str,
                "url": decision.get("url"),
                "target": target_dict,
                "value": decision.get("value"),
                "input_param": decision.get("input_param"),
                "output_param": decision.get("output_param"),
                "expectation": decision.get("expectation"),
                "is_risky": decision.get("is_risky", policy_dec.is_risky),
                "description": decision.get("reason")
            }
            trajectory.append(step_record)

            # Execute action on live surface
            if action_str == "navigate" and decision.get("url"):
                self.surface.navigate(decision["url"])
            elif action_str == "click" and loc_spec:
                self.surface.click(loc_spec)
            elif action_str == "fill" and loc_spec:
                fill_val = decision.get("value", "")
                if fill_val == "{{member_id}}":
                    fill_val = "12345"
                self.surface.fill(loc_spec, fill_val)
            elif action_str == "read" and loc_spec:
                val = self.surface.read(loc_spec)
                log_lines.append(f"Read surface value: '{val}'")
            elif action_str == "wait":
                self.surface.wait(timeout_ms=1000)

            time.sleep(0.3)

        # Capture final discovery screenshot
        screenshot_path = os.path.join(evidence_dir, "discovery.png")
        self.surface.screenshot(screenshot_path)
        log_lines.append(f"Discovery screenshot saved to {screenshot_path}")

        # Define inputs and outputs schemas
        inputs_def = {
            "member_id": InputParamDef(type="string", required=True, default="12345", description="Target Member ID")
        }
        outputs_def = {
            "savings_balance": OutputParamDef(type="number", description="Current savings account balance"),
            "currency": OutputParamDef(type="string", description="Currency code (USD)")
        }

        # Compile trajectory into CapabilityArtifact
        artifact = compile_trajectory_to_artifact(
            trajectory=trajectory,
            capability_id=capability_id,
            description=f"Automated capability for goal: {goal}",
            inputs=inputs_def,
            outputs=outputs_def,
            checkpoint=final_checkpoint
        )

        # Write discovery evidence logs and artifact
        with open(os.path.join(evidence_dir, "discovery.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))

        with open(os.path.join(evidence_dir, "discovery.json"), "w", encoding="utf-8") as f:
            json.dump({
                "goal": goal,
                "capability_id": capability_id,
                "trajectory": trajectory,
                "total_steps": len(trajectory)
            }, f, indent=2)

        with open(os.path.join(evidence_dir, "artifact.json"), "w", encoding="utf-8") as f:
            f.write(artifact.model_dump_json(indent=2))

        return artifact
