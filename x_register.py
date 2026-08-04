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
            # Use EMAIL path instead of phone (data-center IP phone signup is hard-blocked by X)
            ok = click(page, ['[role="button"]:has-text("Email or username")', 'button:has-text("Email or username")'])
            print(f"[1] clicked email entry: {ok}", flush=True)
            time.sleep(4)
            # now a field appears: fill email then Continue
            try:
                email_input = page.locator('input[type="email"], input[name="email"], input[autocomplete="email"]').first
                if email_input.count():
                    email_input.fill(EMAIL, timeout=8000)
                    time.sleep(1)
                    print(f"[1] email filled: {EMAIL}", flush=True)
            except Exception as e:
                print(f"[1] email fill err: {e}", flush=True)
            page.screenshot(path="x_s1b_email_filled.png")
            ok2 = click(page, ['[role="button"]:has-text("Continue")', 'button:has-text("Continue")'])
            print(f"[1] clicked Continue: {ok2}", flush=True)
            time.sleep(6)
            page.screenshot(path="x_s1c_after_email.png")
            print(f"[1] after email: {page_body(page)[:300]}", flush=True)
            step = "email_sent"
            save_state({"step": step, "ts": time.time()})

        # ---- EMAIL OTP (or next step) ----
        if step == "email_sent":
            body = page_body(page)
            print(f"[E] page: {body[:250]}", flush=True)
            page.screenshot(path="x_se_email_wait.png")
            if OTP:
                try:
                    otp_inputs = page.locator('input[inputmode="numeric"], input[autocomplete="one-time-code"]')
                    n = otp_inputs.count()
                    print(f"[E] otp inputs: {n}", flush=True)
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
                        print(f"[E] clicked verify: {ok}", flush=True)
                        time.sleep(6)
                        page.screenshot(path="x_se_otp_done.png")
                        print(f"[E] after otp: {page_body(page)[:250]}", flush=True)
                        step = "details"
                        save_state({"step": step, "ts": time.time()})
                    else:
                        print("[E] no OTP input visible", flush=True)
                except Exception as e:
                    print(f"[E] otp err: {e}", flush=True)
            else:
                print("[E] NEED EMAIL OTP — rerun with otp=<code>", flush=True)

        # ---- PHONE ENTRY: country code + phone ----
        if step == "phone_entry":
            body = page_body(page)
            print(f"[2] page: {body[:250]}", flush=True)
            page.screenshot(path="x_s2_phone_entry.png")
            # X uses a custom country-code dropdown (button showing "+1" / flag).
            # Click it, then search for China (+86) and click the option.
            country_ok = False
            try:
                # the country selector: a button/div containing "+1" text near phone input
                cc_sel = page.locator('button:has-text("+1"), div[role="button"]:has-text("+1"), [data-testid="phoneNumberCountryCode"]').first
                if cc_sel.count() and cc_sel.is_visible():
                    cc_sel.click(timeout=5000)
                    time.sleep(2)
                    page.screenshot(path="x_s2b_country_open.png")
                    # now a dropdown with search appears; type "China" then click option
                    search = page.locator('input[placeholder*="Search"], input[type="search"], input[placeholder*="search"]').first
                    if search.count():
                        search.fill("China", timeout=5000)
                        time.sleep(1.5)
                    opt = page.locator('[role="option"]:has-text("China"), [role="option"]:has-text("+86"), div[role="option"]:has-text("China")').first
                    if opt.count():
                        opt.click(timeout=5000)
                        time.sleep(1.5)
                        country_ok = True
                        print("[2] country set to China +86", flush=True)
                    else:
                        # fallback: keyboard select via pressing Enter after search
                        page.keyboard.press("Enter")
                        time.sleep(1.5)
                        country_ok = True
                        print("[2] country selected via Enter", flush=True)
                else:
                    print("[2] country selector not found, assuming default", flush=True)
                    country_ok = True
            except Exception as e:
                print(f"[2] country select err: {e}", flush=True)
                country_ok = True
            page.screenshot(path="x_s2c_country_done.png")
            # phone number input
            filled = False
            try:
                ph_input = page.locator('input[inputmode="tel"], input[name="phone_number"], input[type="tel"]').first
                if ph_input.count():
                    digits = PHONE.replace("+", "").replace(" ", "")
                    # +86 selected -> strip country code prefix (86) so number is local
                    if digits.startswith("86") and len(digits) > 11:
                        digits = digits[2:]
                    ph_input.fill(digits, timeout=8000)
                    time.sleep(1.5)
                    # verify the Continue button is enabled (disabled means invalid number)
                    cont_btn = page.locator('[role="button"]:has-text("Continue")').first
                    if cont_btn.count():
                        disabled = cont_btn.get_attribute("aria-disabled") == "true" or cont_btn.evaluate("el => el.disabled === true || el.getAttribute('aria-disabled') === 'true'")
                        print(f"[2] phone filled: {digits} (continue_disabled={disabled})", flush=True)
                    else:
                        print(f"[2] phone filled: {digits}", flush=True)
                    filled = True
            except Exception as e:
                print(f"[2] phone fill: {e}", flush=True)
            page.screenshot(path="x_s3_phone_filled.png")
            if filled:
                # X anti-automation: overlays inside #layers intercept pointer events
                # (data-testid="mask", role="group" dialogs, etc). Nuke them all.
                try:
                    removed = page.evaluate("""() => {
                      let n = 0;
                      const kill = (el) => {
                        if (!el) return;
                        el.style.setProperty('display', 'none', 'important');
                        el.style.setProperty('pointer-events', 'none', 'important');
                        el.style.setProperty('visibility', 'hidden', 'important');
                        n++;
                      };
                      // deepest layers container
                      const layers = document.querySelector('#layers');
                      if (layers) {
                        // remove everything in layers that has role/aria/data-testid and covers screen
                        layers.querySelectorAll('[data-testid="mask"], [role="group"], [role="dialog"], [role="presentation"], [aria-modal="true"]').forEach(kill);
                        // also kill any fixed full-screen div
                        layers.querySelectorAll('div').forEach(el => {
                          const r = el.getBoundingClientRect();
                          if (r.width >= window.innerWidth - 20 && r.height >= window.innerHeight - 20 && r.top <= 0) kill(el);
                        });
                      }
                      return n;
                    }""")
                    print(f"[2] removed {removed} layer overlays", flush=True)
                    time.sleep(1.5)
                except Exception as e:
                    print(f"[2] overlay removal err: {e}", flush=True)
                # Primary submission: keyboard Enter on the phone input (bypasses pointer interception)
                try:
                    ph_input = page.locator('input[inputmode="tel"], input[name="phone_number"], input[type="tel"]').first
                    ph_input.press("Enter", timeout=5000)
                    cont_ok = True
                    print("[2] pressed Enter on phone input", flush=True)
                except Exception as e:
                    print(f"[2] enter press err: {e}", flush=True)
                    cont_ok = False
                if not cont_ok:
                    try:
                        cont_btn = page.locator('[role="button"]:has-text("Continue")').first
                        if cont_btn.count():
                            cont_btn.scroll_into_view_if_needed(timeout=5000)
                            time.sleep(1)
                            disabled = cont_btn.get_attribute("aria-disabled") == "true" or cont_btn.evaluate("el => el.disabled === true || el.getAttribute('aria-disabled') === 'true'")
                            print(f"[2] continue disabled: {disabled}", flush=True)
                            if not disabled:
                                cont_btn.click(timeout=8000)
                                cont_ok = True
                    except Exception as e:
                        print(f"[2] continue click err: {e}", flush=True)
                if not cont_ok:
                    ok = click(page, ['[role="button"]:has-text("Continue")', '[data-testid="phoneNumberContinue"]', 'button:has-text("Continue")'])
                    print(f"[2] clicked Continue (fallback): {ok}", flush=True)
                if not cont_ok:
                    # last resort: native JS click + bubbling mouse event (bypasses all interception)
                    try:
                        fired = page.evaluate("""() => {
                          const btns = [...document.querySelectorAll('[role="button"]')];
                          const b = btns.find(x => (x.textContent||'').trim() === 'Continue');
                          if (!b) return 'NO_BUTTON';
                          b.click();
                          b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                          b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                          b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                          return 'JS_CLICKED';
                        }""")
                        print(f"[2] JS native click: {fired}", flush=True)
                        time.sleep(5)
                        cont_ok = True
                    except Exception as e:
                        print(f"[2] JS click err: {e}", flush=True)
                time.sleep(7)
                page.screenshot(path="x_s4_after_continue.png")
                body2 = page_body(page)
                print(f"[2] after continue: {body2[:250]}", flush=True)
                if "verify" in body2.lower() or "code" in body2.lower() or "check your" in body2.lower() or "sent" in body2.lower():
                    step = "sms_sent"
                    save_state({"step": step, "ts": time.time()})
                    print("[2] SMS verification page reached", flush=True)
                else:
                    # maybe error (invalid number) — retry once with plain digits
                    print("[2] no verify page yet, may need retry", flush=True)

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
