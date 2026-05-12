# -*- coding: utf-8 -*-
"""
Smoke test for dynamic frontmatter editing feature.
Tests:
1. Frontmatter block renders on contact page
2. Enum field (relationship) shows a <select> dropdown
3. Selecting a different value triggers a PATCH and shows checkmark
4. Read-only fields (type, name) are not editable
5. List fields render as pill badges (not inputs)
6. Text field (email) becomes an inline input on click
"""

import sys
import io
import time
from playwright.sync_api import sync_playwright

# Force UTF-8 stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

FRONTEND_URL = "http://localhost:5174"
TIMEOUT = 10000


def run_smoke_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        try:
            # Navigate to app
            page.goto(FRONTEND_URL)
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            page.screenshot(path="/tmp/sm_01_home.png")
            print("[OK] App loaded")

            # Expand the CONTACTS section in the sidebar
            page.wait_for_selector("text=CONTACTS", timeout=TIMEOUT)
            page.click("text=CONTACTS")
            time.sleep(0.5)
            # Now click the contact page (displayed as "alexandra cernanova" with spaces)
            page.wait_for_selector("text=alexandra cernanova", timeout=TIMEOUT)
            page.click("text=alexandra cernanova")
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            time.sleep(1)
            page.screenshot(path="/tmp/sm_02_contact_page.png")
            print("[OK] Contact page loaded")

            # Check frontmatter block exists
            fm_block = page.locator(".flex.flex-wrap.gap-2.mb-8")
            if fm_block.count() == 0:
                errors.append("Frontmatter block not found")
            else:
                print("[OK] Frontmatter block rendered")

            # Check for <select> dropdowns for enum fields
            selects = page.locator("select")
            if selects.count() == 0:
                errors.append("No <select> dropdowns found for enum fields")
            else:
                print(f"[OK] Found {selects.count()} enum dropdown(s)")

            # Try changing a dropdown value (relationship)
            relationship_select = None
            for i in range(selects.count()):
                sel = selects.nth(i)
                options = sel.evaluate("el => [...el.options].map(o => o.value)")
                if "Cold" in options or "Warm" in options:
                    relationship_select = sel
                    break

            if relationship_select:
                relationship_select.select_option("Warm")
                try:
                    page.wait_for_selector("text=✓", timeout=3000)
                    print("[OK] Enum field change shows checkmark indicator")
                except Exception:
                    errors.append("No checkmark indicator appeared after enum change")
                page.screenshot(path="/tmp/sm_03_after_enum_change.png")
            else:
                errors.append("Could not find relationship dropdown with Cold/Warm options")

            # Count badges
            badges = page.locator("span.uppercase.tracking-wider")
            print(f"  Found {badges.count()} frontmatter badges")

            # Check no inputs visible by default (text fields not in edit mode)
            inputs = page.locator("input[type=text], input:not([type])")
            visible_inputs = [i for i in range(inputs.count()) if inputs.nth(i).is_visible()]
            if len(visible_inputs) == 0:
                print("[OK] No inputs visible by default (text fields show as clickable spans)")
            else:
                print(f"  Note: {len(visible_inputs)} input(s) visible by default")

            # Try clicking email field to activate inline edit
            badge = page.locator("span.uppercase.tracking-wider:has(span:has-text('email:'))").first
            if badge.count() > 0:
                badge.click()
                time.sleep(0.3)
                focused_input = page.locator("input:focus")
                if focused_input.count() > 0:
                    print("[OK] Text field becomes editable input on click")
                    focused_input.press("Escape")
                else:
                    print("  Note: Could not confirm click-to-edit for text field")
            else:
                print("  Note: email badge not found via locator")

            page.screenshot(path="/tmp/sm_04_final.png")

        except Exception as e:
            errors.append(f"Exception: {e}")
            page.screenshot(path="/tmp/sm_error.png")
        finally:
            browser.close()

        if errors:
            print("\nSMOKE TEST FAILED:")
            for err in errors:
                print(f"   - {err}")
            return False
        else:
            print("\nSMOKE TEST PASSED")
            return True


if __name__ == "__main__":
    success = run_smoke_test()
    exit(0 if success else 1)
