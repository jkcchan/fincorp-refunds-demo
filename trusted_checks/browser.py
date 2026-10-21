#!/usr/bin/env python3
"""Controller-owned Playwright outcome checks, run against actual HTTP revisions."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/")
SCENARIO = sys.argv[2] if len(sys.argv) > 2 else "smoke"
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        if SCENARIO == "case-link-review":
            change_id = sys.argv[3]
            page.goto(URL + "/login/")
            page.locator('input[name="username"]').fill("toolsadmin")
            page.locator('input[name="password"]').fill("tools-demo-2026")
            page.get_by_role("button", name="Sign in").click()
            page.goto(URL + f"/changes/{change_id}/")
            assert page.get_by_role("button", name="Approve change").count() == 1
            frame = page.frame_locator("iframe.preview")
            frame.locator('input[name="username"]').fill("ops")
            frame.locator('input[name="password"]').fill("ops-demo-2026")
            with page.expect_response(lambda response: response.request.method == "POST" and "/login/" in response.url):
                frame.get_by_role("button", name="Sign in").click()
            frame.get_by_role("link", name="RF-1009").click()
            frame.get_by_role("button", name="Copy case link").click()
            frame.get_by_text("Case link copied.").wait_for(state="visible", timeout=5000)
            page.screenshot(path=str(ARTIFACTS / f"{SCENARIO}-{change_id}.png"), full_page=True)
            print(f"PASS {SCENARIO} #{change_id}: link works inside review preview")
            browser.close()
            return
        if SCENARIO == "session-isolation":
            # One browser context shares cookies across these ports.
            preview = sys.argv[3].rstrip("/")
            page.goto(URL + "/login/")
            page.locator('input[name="username"]').fill("ops")
            page.locator('input[name="password"]').fill("ops-demo-2026")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(URL + "/")
            page.goto(preview + "/login/")
            page.locator('input[name="username"]').fill("ops2")
            page.locator('input[name="password"]').fill("ops2-demo-2026")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(preview + "/")
            page.goto(URL + "/")
            assert page.url == URL + "/", f"runtime session lost after preview login: {page.url}"
            assert page.locator(".user").inner_text() == "ops", "runtime session was overwritten by preview login"
            page.goto(preview + "/")
            assert page.url == preview + "/", f"preview session lost after runtime login: {page.url}"
            assert page.locator(".user").inner_text() == "ops2", "preview session was overwritten by runtime login"
            print(f"PASS session-isolation: {URL} holds ops, {preview} holds ops2")
            browser.close()
            return
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL + "/login/")
        page.locator('input[name="username"]').fill("ops")
        page.locator('input[name="password"]').fill("ops-demo-2026")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_url(URL + "/")
        assert page.get_by_role("heading", name="Refund", exact=False).count() > 0
        assert page.get_by_text("Synthetic data").count() > 0
        if SCENARIO in ("queue-intro-red", "queue-intro-green"):
            expected = ("Review requets" if SCENARIO.endswith("red") else "Review requests") + " and track every decision."
            assert page.get_by_text(expected, exact=True).is_visible()
            assert not errors, errors
            page.screenshot(path=str(ARTIFACTS / f"{SCENARIO}-{URL.split(':')[-1]}.png"), full_page=True)
            print(f"PASS {SCENARIO} at {URL}: {expected}")
            browser.close()
            return
        if SCENARIO in ("case-link-red", "case-link-green"):
            page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=URL)
            page.goto(URL + "/cases/RF-1009/")
            assert page.get_by_text("PAY-MAPLE-008").count() > 0
            button = page.get_by_role("button", name="Copy case link")
            button.wait_for(state="visible")
            page.evaluate("navigator.clipboard.writeText('original clipboard value')")
            button.click()
            feedback = page.locator("#copy-link-result")
            if SCENARIO.endswith("green"):
                feedback.get_by_text("Case link copied.").wait_for(state="visible", timeout=5000)
                assert page.evaluate("navigator.clipboard.readText()") == URL + "/cases/RF-1009/"
            else:
                page.wait_for_timeout(350)
                assert feedback.inner_text() == "", "Broken baseline unexpectedly displayed feedback"
                assert page.evaluate("navigator.clipboard.readText()") == "original clipboard value"
            assert not errors, errors
            page.screenshot(path=str(ARTIFACTS / f"{SCENARIO}-{URL.split(':')[-1]}.png"), full_page=True)
            print(f"PASS {SCENARIO} at {URL}: actual clipboard and feedback checked")
            browser.close()
            return
        if SCENARIO == "copy":
            assert page.get_by_role("heading", name="Refund requests").count() == 1
        if SCENARIO.startswith("feature"):
            page.locator('select[name="status"]').select_option("new")
            page.locator('select[name="assignee"]').select_option("mine")
            page.get_by_role("button", name="Apply filters").click()
            assert page.get_by_text("RF-1001").count() == 0
            assert page.locator('select[name="status"]').input_value() == "new"
            if SCENARIO == "feature-revision":
                page.locator('select[name="assignee"]').select_option("unassigned")
                page.get_by_role("button", name="Apply filters").click()
                assert page.locator('select[name="status"]').input_value() == "new"
                assert page.locator('select[name="assignee"]').input_value() == "unassigned"
        if SCENARIO in ("bug", "crash-expected"):
            page.goto(URL + "/cases/RF-LEGACY-NULL/")
            page.wait_for_timeout(450)
            assert page.get_by_text("RF-LEGACY-NULL").count() > 0
            if SCENARIO == "crash-expected":
                assert any("trim" in error for error in errors), f"Baseline did not actually crash: {errors}"
                assert page.locator("#note-preview").inner_text() == "Loading note…"
                print("PASS actual baseline pageerror:", errors)
            else:
                assert not errors, f"Candidate still crashes: {errors}"
                assert page.locator("#note-preview").inner_text() == "No notes yet."
                print("PASS legacy row retained and renders without pageerror")
        else:
            page.goto(URL + "/cases/RF-1001/")
            assert page.get_by_text("PAY-ASTER-001").count() >= 1
            assert not errors, f"Unexpected browser errors: {errors}"
        page.screenshot(path=str(ARTIFACTS / f"{SCENARIO}-{URL.split(':')[-1]}.png"), full_page=True)
        print(f"PASS {SCENARIO} at {URL} screenshot saved")
        browser.close()


if __name__ == "__main__":
    main()
