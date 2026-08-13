"""Playwright Surface Abstraction implementing multi-tiered locators."""
import os
import time
from typing import Dict, Any, List, Optional
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from app.surface.base import Surface
from app.surface.locator import LocatorSpec

class PlaywrightSurface(Surface):
    """Playwright implementation of the Surface protocol."""

    def __init__(self, page: Page):
        self.page = page

    def resolve_locator(self, spec: LocatorSpec) -> Locator:
        """
        Resolve Playwright Locator using Priority Strategy:
        1. Role + Accessible Name
        2. Label text
        3. Semantic attributes (id, name, data-test)
        4. Visible text
        5. CSS fallback
        """
        # Strategy 1: Role + Accessible Name
        if spec.role:
            try:
                kwargs = {}
                if spec.name:
                    kwargs["name"] = spec.name
                loc = self.page.get_by_role(spec.role, **kwargs)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass

        # Strategy 2: Label text
        if spec.label:
            try:
                loc = self.page.get_by_label(spec.label)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass

        # Strategy 3: Semantic attributes
        if spec.semantic_attr:
            for attr_name, attr_val in spec.semantic_attr.items():
                try:
                    loc = self.page.locator(f"[{attr_name}='{attr_val}']")
                    if loc.count() > 0:
                        return loc.first
                except Exception:
                    pass

        # Strategy 4: Visible inner text
        if spec.text:
            try:
                loc = self.page.get_by_text(spec.text, exact=False)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass

        # Strategy 5: CSS Fallback
        if spec.css_fallback:
            try:
                loc = self.page.locator(spec.css_fallback)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass

        # Final fallback attempt: if css_fallback provided, use it anyway so playwright raises clean timeout
        if spec.css_fallback:
            return self.page.locator(spec.css_fallback).first

        # Fallback to text search if present
        if spec.text:
            return self.page.get_by_text(spec.text).first

        raise ValueError(f"Could not construct valid selector from LocatorSpec: {spec.model_dump_json()}")

    def observe(self) -> Dict[str, Any]:
        """Inspect and return structured DOM state for LLM decision making."""
        url = self.page.url
        title = self.page.title()
        
        # Extract interactive elements & main content
        elements_js = """
        () => {
            const items = [];
            const interactive = document.querySelectorAll('a, button, input, select, textarea, [role="button"]');
            interactive.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    items.push({
                        index: index,
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        name: el.name || null,
                        type: el.type || null,
                        text: (el.innerText || el.value || '').trim(),
                        label: el.labels && el.labels.length ? el.labels[0].innerText.trim() : null,
                        placeholder: el.placeholder || null,
                        role: el.getAttribute('role') || el.tagName.toLowerCase()
                    });
                }
            });
            
            // Extract body text snippet
            const bodyText = document.body.innerText.substring(0, 1500);
            return { elements: items, bodyText: bodyText };
        }
        """
        result = self.page.evaluate(elements_js)
        return {
            "url": url,
            "title": title,
            "interactive_elements": result.get("elements", []),
            "visible_text_snippet": result.get("bodyText", "")
        }

    def click(self, locator: LocatorSpec) -> None:
        loc = self.resolve_locator(locator)
        loc.scroll_into_view_if_needed()
        loc.click(timeout=5000)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=1000)
        except Exception:
            pass

    def fill(self, locator: LocatorSpec, value: str) -> None:
        loc = self.resolve_locator(locator)
        loc.scroll_into_view_if_needed()
        loc.fill(value, timeout=5000)

    def navigate(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=10000)

    def read(self, locator: LocatorSpec) -> str:
        loc = self.resolve_locator(locator)
        if loc.count() == 0:
            return ""
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
        if tag in ["input", "textarea", "select"]:
            return loc.input_value() or loc.text_content() or ""
        return loc.text_content() or ""

    def wait(self, timeout_ms: int = 2000, locator: Optional[LocatorSpec] = None) -> None:
        if locator:
            loc = self.resolve_locator(locator)
            loc.wait_for(state="visible", timeout=timeout_ms)
        else:
            self.page.wait_for_timeout(timeout_ms)

    def screenshot(self, path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.page.screenshot(path=path, full_page=True)
        return os.path.abspath(path)
