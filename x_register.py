#!/usr/bin/env python3
"""X (Twitter) account registration — phone-first flow, loop-driven.

State persists by committing x_state.json + x_cookies.json back to the repo
(workflow does `git add && git commit && git push` after this script runs).
Loop continues through as many steps as possible in one run.
"""
import json, os, sys, time

EMAIL = os.environ.get("X_EMAIL", "")
USERNAME = os.environ.get("X_USERNAME", "")
PASSWORD = os.environ.get("X_PASSWORD", "")
PHONE = os.environ.get("X_PHONE", "")
OTP = os.environ.get("X_OTP", "")

STATE_FILE = "x_state.json"
COOKIE_FILE = "x_cookies.json"

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"step": "start"}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)
    print(f"[state] step={s.get('step')}", flush=True)

def click(page, selectors, timeout=8000):
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=timeout)
                return True
        except Exception:
            pass
    return False

def page_body(page):
    try:
        return page.inner_text("body")[:600]
    except Exception:
        return ""

from playwright.sync_api import sync_playwright

def main():
    state = load_state()
    step = state.get("step", "start")
    print(f"[cfg] phone={PHONE[-4:] if PHONE else '?'} otp_given={bool(OTP)} step={step}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()

        # ---- START: open signup ----
        if step == "start":
            print("[1] open x.com/signup", flush=True)
            page.goto("https://x.com/signup", timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
            print(f"[1] page: {page_body(page)[:250]}", flush=True)
            page.screenshot(path="x_s1_home.png")
            ok = click(page, ['[role="button"]:has-text("Continue with phone")', 'button:has-text("Continue with phone")'])
            print(f"[1] clicked phone entry: {ok}", flush=True)
            time.sleep(4)
            step = "phone_entry"
            save_state({"step": step, "ts": time.time()})

        # ---- PHONE ENTRY: country code + phone ----
        if step == "phone_entry":
            body = page_body(page)
            print(f"[2] page: {body[:250]}", flush=True)
            page.screenshot(path="x_s2_phone_entry.png")
            # X phone form: country select + phone input
            filled = False
            try:
                # country code: select element
                for sel in ['select', 'select[name="phoneCountry"]']:
                    try:
                        sel_el = page.locator(sel).first
                        if sel_el.count():
                            opts = sel_el.locator("option")
                            n = opts.count()
                            # find option with value starting with +86 or text CN/China/+86
                            target = None
                            for i in range(n):
                                v = opts.nth(i).get_attribute("value") or ""
                                t = opts.nth(i).inner_text()
                                if "86" in v or "China" in t or "CN" in v.upper():
                                    target = i
                                    break
                            if target is not None:
                                opts.nth(target).select_option(value=opts.nth(target).get_attribute("value"))
                                print(f"[2] country selected idx={target}", flush=True)
                                time.sleep(1)
                            break
                    except Exception:
                        pass
                # phone number input
                ph_input = page.locator('input[inputmode="tel"], input[name="phone_number"], input[type="tel"]').first
                if ph_input.count():
                    digits = PHONE.replace("+", "").replace(" ", "")
                    ph_input.fill(digits, timeout=8000)
                    time.sleep(1)
                    filled = True
                    print(f"[2] phone filled: {digits}", flush=True)
            except Exception as e:
                print(f"[2] phone fill: {e}", flush=True)
            page.screenshot(path="x_s3_phone_filled.png")
            if filled:
                ok = click(page, ['[role="button"]:has-text("Next")', 'button:has-text("Next")'])
                print(f"[2] clicked Next: {ok}", flush=True)
                time.sleep(5)
                page.screenshot(path="x_s4_after_next.png")
                body2 = page_body(page)
                print(f"[2] after next: {body2[:250]}", flush=True)
                step = "sms_sent"
                save_state({"step": step, "ts": time.time()})
                print("[2] phone submitted — SMS should be sent", flush=True)

        # ---- SMS OTP ----
        if step == "sms_sent":
            body = page_body(page)
            print(f"[3] page: {body[:250]}", flush=True)
            page.screenshot(path="x_s5_sms_wait.png")
            if OTP:
                try:
                    otp_inputs = page.locator('input[inputmode="numeric"], input[autocomplete="one-time-code"]')
                    n = otp_inputs.count()
                    print(f"[3] otp inputs: {n}", flush=True)
                    if n >= 1:
                        if n > 1:
                            for idx, ch in enumerate(OTP):
                                if idx < n:
                                    otp_inputs.nth(idx).fill(ch)
                                    time.sleep(0.3)
                        else:
                            otp_inputs.first.fill(OTP)
                        time.sleep(1)
                        ok = click(page, ['[role="button"]:has-text("Verify")', 'button:has-text("Next")'])
                        print(f"[3] clicked verify: {ok}", flush=True)
                        time.sleep(6)
                        page.screenshot(path="x_s6_otp_done.png")
                        body3 = page_body(page)
                        print(f"[3] after otp: {body3[:250]}", flush=True)
                        step = "details"
                        save_state({"step": step, "ts": time.time()})
                    else:
                        print("[3] no OTP input visible", flush=True)
                except Exception as e:
                    print(f"[3] otp err: {e}", flush=True)
            else:
                print("[3] NEED OTP — rerun with otp=<code>", flush=True)

        # ---- DETAILS: name / username / password ----
        if step == "details":
            body = page_body(page)
            print(f"[4] page: {body[:300]}", flush=True)
            page.screenshot(path="x_s7_details.png")
            try:
                name_input = page.locator('input[name="name"], input[autocomplete="name"]').first
                if name_input.count():
                    name_input.fill("Liu Daluo", timeout=6000)
                    time.sleep(0.5)
                    print("[4] name filled", flush=True)
            except Exception as e:
                print(f"[4] name: {e}", flush=True)
            try:
                pw = page.locator('input[type="password"], input[name="password"]').first
                if pw.count():
                    pw.fill(PASSWORD, timeout=6000)
                    time.sleep(0.5)
                    print("[4] password filled", flush=True)
            except Exception as e:
                print(f"[4] pw: {e}", flush=True)
            try:
                un = page.locator('input[name="username"], input[autocomplete="username"]').first
                if un.count():
                    un.fill(USERNAME, timeout=6000)
                    time.sleep(0.5)
                    print("[4] username filled", flush=True)
            except Exception as e:
                print(f"[4] user: {e}", flush=True)
            page.screenshot(path="x_s8_details_filled.png")
            ok = click(page, ['[role="button"]:has-text("Sign up")', 'button:has-text("Sign up")', '[data-testid="signup"]'])
            print(f"[4] clicked signup: {ok}", flush=True)
            time.sleep(8)
            page.screenshot(path="x_s9_final.png")
            body4 = page_body(page)
            print(f"[4] final: {body4[:250]}", flush=True)
            # save cookies + state
            try:
                cookies = ctx.cookies()
                with open(COOKIE_FILE, "w") as f:
                    json.dump(cookies, f)
                print(f"[4] cookies saved ({len(cookies)})", flush=True)
                step = "done"
                save_state({"step": step, "ts": time.time()})
            except Exception as e:
                print(f"[4] cookie err: {e}", flush=True)

        browser.close()
        print(f"[end] reached step={step}", flush=True)

if __name__ == "__main__":
    main()
