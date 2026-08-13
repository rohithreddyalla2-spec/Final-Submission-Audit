"""Deterministic Replay Engine executing Capability Artifacts step-by-step without LLM calls."""
import time
import jinja2
from typing import Dict, Any, Optional
from app.artifacts.schema import CapabilityArtifact, Step, StepAction, CheckpointType
from app.surface.base import Surface
from app.safety.policy import SafetyPolicy, PolicyDecision
from app.replay.result import ReplayResult, ReplayStatus, ErrorCode

class ReplayEngine:
    """Deterministic Replay Engine executing structured capability artifacts."""

    def __init__(self, surface: Surface, policy: Optional[SafetyPolicy] = None):
        self.surface = surface
        self.policy = policy or SafetyPolicy()

    def _render_value(self, template_str: Optional[str], params: Dict[str, Any]) -> Optional[str]:
        if not template_str:
            return template_str
        try:
            return jinja2.Template(template_str).render(**params)
        except Exception:
            return template_str

    def _check_page_fault_states(self, obs: Dict[str, Any]) -> Optional[ReplayResult]:
        """Inspect page text/DOM for known business outcomes or system fault banners."""
        snippet = obs.get("visible_text_snippet", "")

        if "MEMBER_NOT_FOUND" in snippet or "Member not found" in snippet:
            return ReplayResult(
                status=ReplayStatus.BUSINESS_OUTCOME,
                code=ErrorCode.MEMBER_NOT_FOUND,
                expected="Member details page",
                observed="Member not found in database",
                error_message="Member ID was not found in records."
            )

        if "VALIDATION_ERROR" in snippet or "Validation Error" in snippet:
            return ReplayResult(
                status=ReplayStatus.BUSINESS_OUTCOME,
                code=ErrorCode.VALIDATION_ERROR,
                expected="Form submitted successfully",
                observed="Validation error message displayed",
                error_message="Form input failed validation rules."
            )

        if "SESSION_TIMEOUT" in snippet or "session has expired" in snippet or "expired=1" in obs.get("url", ""):
            return ReplayResult(
                status=ReplayStatus.HARD_FAILURE,
                code=ErrorCode.SESSION_TIMEOUT,
                expected="Authenticated page access",
                observed="Session timeout / redirected to login",
                error_message="Session expired or authorization invalid."
            )

        if "APPLICATION_ERROR" in snippet or "500 Internal Server Error" in snippet:
            return ReplayResult(
                status=ReplayStatus.HARD_FAILURE,
                code=ErrorCode.APPLICATION_ERROR,
                expected="Normal HTTP 200 response",
                observed="HTTP 500 Application Error",
                error_message="Banking application encountered an internal server error."
            )

        if "unexpected-dialog-overlay" in snippet or "System Maintenance Alert" in snippet:
            return ReplayResult(
                status=ReplayStatus.RECOVERABLE_FAILURE,
                code=ErrorCode.UNEXPECTED_DIALOG,
                expected="Clean page without overlay",
                observed="Blocking maintenance dialog detected",
                error_message="An unexpected interstitial dialog blocked execution."
            )

        return None

    def execute(
        self,
        artifact: CapabilityArtifact,
        input_params: Dict[str, Any],
        handoff_manager: Optional[Any] = None
    ) -> ReplayResult:
        """
        Replay capability artifact deterministically.
        NO LLM DECISION-MAKING DURING REPLAY.
        """
        start_time = time.time()
        outputs_collected: Dict[str, Any] = {}

        # Fill default input values if missing
        merged_inputs = {}
        for k, v_def in artifact.inputs.items():
            if k in input_params:
                merged_inputs[k] = input_params[k]
            elif v_def.default is not None:
                merged_inputs[k] = v_def.default
            elif v_def.required:
                return ReplayResult(
                    status=ReplayStatus.HARD_FAILURE,
                    code=ErrorCode.UNKNOWN_ERROR,
                    capability_id=artifact.capability_id,
                    error_message=f"Missing required input parameter '{k}'"
                )

        for step in artifact.steps:
            # 1. Render dynamic values using inputs
            step_url = self._render_value(step.url, merged_inputs)
            step_val = self._render_value(step.value, merged_inputs)
            if step.input_param and step.input_param in merged_inputs:
                step_val = str(merged_inputs[step.input_param])

            # 2. Safety Policy Evaluation
            policy_dec = self.policy.evaluate_action(
                action=step.action,
                url=step_url,
                locator=step.locator,
                value=step_val,
                description=step.description
            )

            if not policy_dec.allowed:
                return ReplayResult(
                    status=ReplayStatus.HARD_FAILURE,
                    code=ErrorCode.SAFETY_POLICY_VIOLATION,
                    step_id=step.step_id,
                    capability_id=artifact.capability_id,
                    error_message=f"Safety Policy Violation: {policy_dec.reason}"
                )

            # Handle risky action handoff if needed
            if (policy_dec.is_risky or step.is_risky) and handoff_manager:
                approved = handoff_manager.request_human_approval(
                    run_id=artifact.capability_id,
                    step_id=step.step_id,
                    reason=policy_dec.reason or "Risky account action requires confirmation.",
                    surface=self.surface
                )
                if not approved:
                    return ReplayResult(
                        status=ReplayStatus.HARD_FAILURE,
                        code=ErrorCode.RISKY_ACTION_PAUSED,
                        step_id=step.step_id,
                        capability_id=artifact.capability_id,
                        error_message="Human operator rejected risky action."
                    )

            # 3. Observe surface pre-step state & check fault banners
            obs_pre = self.surface.observe()
            fault_res = self._check_page_fault_states(obs_pre)
            if fault_res:
                fault_res.capability_id = artifact.capability_id
                fault_res.step_id = step.step_id
                fault_res.execution_time_ms = (time.time() - start_time) * 1000
                return fault_res

            # 4. Perform deterministic action
            try:
                if step.action == StepAction.NAVIGATE:
                    if not step_url:
                        raise ValueError(f"Step '{step.step_id}' missing URL for navigate action")
                    self.surface.navigate(step_url)

                elif step.action == StepAction.CLICK:
                    if not step.locator:
                        raise ValueError(f"Step '{step.step_id}' missing locator for click action")
                    self.surface.click(step.locator)

                elif step.action == StepAction.FILL:
                    if not step.locator:
                        raise ValueError(f"Step '{step.step_id}' missing locator for fill action")
                    self.surface.fill(step.locator, step_val or "")

                elif step.action == StepAction.READ:
                    if not step.locator:
                        raise ValueError(f"Step '{step.step_id}' missing locator for read action")
                    val = self.surface.read(step.locator)
                    if step.output_param:
                        import re
                        match = re.search(r"[\d]+\.?[\d]*", val.replace(",", ""))
                        if match:
                            try:
                                outputs_collected[step.output_param] = float(match.group(0))
                            except ValueError:
                                outputs_collected[step.output_param] = val.strip()
                        else:
                            outputs_collected[step.output_param] = val.strip()

                elif step.action == StepAction.WAIT:
                    wait_time = int(step_val) if (step_val and step_val.isdigit()) else 1000
                    self.surface.wait(timeout_ms=wait_time)

            except Exception as e:
                # Locator or execution failure
                return ReplayResult(
                    status=ReplayStatus.HARD_FAILURE,
                    code=ErrorCode.LOCATOR_FAILURE,
                    step_id=step.step_id,
                    capability_id=artifact.capability_id,
                    expected=f"Successful {step.action.value} on {step.locator.describe() if step.locator else 'target'}",
                    observed=str(e),
                    error_message=f"Replay action failed: {str(e)}",
                    execution_time_ms=(time.time() - start_time) * 1000
                )

            # 5. Observe post-action state & check fault banners
            obs_post = self.surface.observe()
            fault_res_post = self._check_page_fault_states(obs_post)
            if fault_res_post:
                fault_res_post.capability_id = artifact.capability_id
                fault_res_post.step_id = step.step_id
                fault_res_post.outputs = outputs_collected
                fault_res_post.execution_time_ms = (time.time() - start_time) * 1000
                return fault_res_post

        # 6. Evaluate Checkpoint
        if artifact.checkpoint:
            cp = artifact.checkpoint
            obs_final = self.surface.observe()
            snippet = obs_final.get("visible_text_snippet", "")
            
            if cp.type == CheckpointType.TEXT_CONTAINS:
                exp_text = self._render_value(cp.expected_value, merged_inputs) or ""
                if exp_text and exp_text.lower() not in snippet.lower():
                    return ReplayResult(
                        status=ReplayStatus.HARD_FAILURE,
                        code=ErrorCode.CHECKPOINT_FAILED,
                        capability_id=artifact.capability_id,
                        expected=f"Page containing text '{exp_text}'",
                        observed=snippet[:200],
                        error_message="Final checkpoint validation failed: expected text not present."
                    )
            elif cp.type == CheckpointType.URL_MATCHES:
                exp_url = self._render_value(cp.expected_value, merged_inputs) or ""
                if exp_url and exp_url not in obs_final.get("url", ""):
                    return ReplayResult(
                        status=ReplayStatus.HARD_FAILURE,
                        code=ErrorCode.CHECKPOINT_FAILED,
                        capability_id=artifact.capability_id,
                        expected=f"URL matching '{exp_url}'",
                        observed=obs_final.get("url", ""),
                        error_message="Final checkpoint validation failed: URL mismatch."
                    )

        total_time = (time.time() - start_time) * 1000
        return ReplayResult(
            status=ReplayStatus.SUCCESS,
            capability_id=artifact.capability_id,
            outputs=outputs_collected,
            execution_time_ms=total_time
        )
