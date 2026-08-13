"""
HttpApiSurface — a minimal Surface adapter for applications accessible via HTTP REST/JSON.

This demonstrates heterogeneous surface support: the same CapabilityArtifact and
ReplayEngine can be driven against a JSON API backend without any Playwright dependency.
The `observe()` call fetches a structured JSON state document; `click`, `fill`, and `read`
map to POST/GET API calls rather than DOM interactions.
"""
from typing import Dict, Any, Optional
import urllib.request
import urllib.parse
import json as _json

from app.surface.base import Surface
from app.surface.locator import LocatorSpec


class HttpApiSurface(Surface):
    """
    Surface implementation that drives a JSON HTTP API instead of a browser.

    Supports applications that expose a structured REST state endpoint alongside
    their UI, enabling the same capability artifact to be replayed deterministically
    against both a browser (PlaywrightSurface) and a headless API (HttpApiSurface).
    """

    def __init__(self, base_url: str, session_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json", **(session_headers or {})}
        self._current_path: str = "/"
        self._last_response: Dict[str, Any] = {}

    # ------------------------------------------------------------------ helpers

    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        url = self.base_url + path
        data = _json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode()
                return _json.loads(raw) if raw else {}
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------ Surface

    def observe(self) -> Dict[str, Any]:
        """
        Fetch a JSON state snapshot from the API.
        Expects the API to expose GET /state returning:
          { "url": "...", "title": "...", "fields": {...}, "text": "..." }
        Falls back to last response if /state is unavailable.
        """
        state = self._request("GET", "/state")
        self._last_response = state
        return {
            "url": state.get("url", self.base_url + self._current_path),
            "title": state.get("title", ""),
            "interactive_elements": state.get("fields", []),
            "visible_text_snippet": state.get("text", _json.dumps(state)[:500]),
        }

    def navigate(self, url: str) -> None:
        """Record the current path for context; send GET to signal page load."""
        path = url.replace(self.base_url, "") or "/"
        self._current_path = path
        self._last_response = self._request("GET", path)

    def click(self, locator: LocatorSpec) -> None:
        """
        Map a click to a POST to a named action endpoint.
        Derives the endpoint from the locator name, css_fallback id, or role+name.
        """
        endpoint = self._locator_to_action_path(locator)
        self._last_response = self._request("POST", endpoint)

    def fill(self, locator: LocatorSpec, value: str) -> None:
        """Map a fill to a PATCH/POST with the field value."""
        field_name = locator.label or locator.name or locator.css_fallback or "field"
        # Strip CSS selector prefix (#)
        field_name = field_name.lstrip("#")
        self._last_response = self._request(
            "PATCH",
            self._current_path,
            body={field_name: value},
        )

    def read(self, locator: LocatorSpec) -> str:
        """Read a field value from the last observed API response."""
        key = (
            locator.output_param
            if hasattr(locator, "output_param") and locator.output_param
            else locator.label or locator.name or ""
        )
        # Attempt semantic_attr id lookup
        if locator.semantic_attr:
            for attr_val in locator.semantic_attr.values():
                if attr_val in self._last_response:
                    return str(self._last_response[attr_val])
        # Direct key lookup
        if key and key in self._last_response:
            return str(self._last_response[key])
        # Fallback: return entire JSON
        return _json.dumps(self._last_response)

    def wait(self, timeout_ms: int = 2000, locator: Optional[LocatorSpec] = None) -> None:
        """No-op: HTTP calls are synchronous; no polling required."""
        pass

    def screenshot(self, path: str) -> str:
        """
        Not natively supported for HTTP APIs; write the last JSON response as evidence.
        """
        import os
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        evidence_path = path.replace(".png", ".json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            _json.dump(self._last_response, f, indent=2)
        return evidence_path

    # ------------------------------------------------------------------ private

    def _locator_to_action_path(self, locator: LocatorSpec) -> str:
        """Derive a REST action endpoint from a LocatorSpec."""
        if locator.css_fallback:
            # e.g. #btn-search-member → /search-member
            slug = locator.css_fallback.lstrip("#btn-").lstrip("#")
            return f"{self._current_path.rstrip('/')}/{slug}"
        if locator.name:
            slug = locator.name.lower().replace(" ", "-").replace("&", "and")
            return f"{self._current_path.rstrip('/')}/{slug}"
        return self._current_path
