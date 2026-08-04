#!/usr/bin/env python3
"""X (Twitter) account registration automation — runs on GitHub Actions overseas runner.

Flow:
  1. Open x.com/signup
  2. Fill name/email/DOB
  3. Verify email (OTP via GitHub secret X_EMAIL_OTP if provided)
  4. Enter phone for SMS verification -> pause, ask operator for code
  5. Set password -> finish -> save cookies for later posting

State is saved to x_state.json so re-runs can resume (register -> email_otp -> sms_otp -> done).
"""
import json, os, sys, time, base64

EMAIL = os.environ.get("X_EMAIL", "")
USERNAME = os.environ.get("X_USERNAME", "")
PASSWORD = os.environ.get("X_PASSWORD", "")
PHONE = os.environ.get("X_PHONE", "")
OTP = os.environ.get("X_OTP", "")
RESUME = os.environ.get("RESUME", "false").lower() == "true"

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
    print(f"[state] step={s.get('step')} saved")

from playwright.sync_api import sync_playwright

def main():
    state = load_state()
    if RESUME:
        print(f"[resume] from step={state.get('step')}")
    print(f"[cfg] email={EMAIL[:4]}*** user={USERNAME} phone={PHONE[-4:] if PHONE else '?'} otp_given={bool(OTP)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
        page = ctx.new_page()

        step = state.get("step", "start")

        # ---- STEP 1: open signup ----
        if step in ("start",):
            print("[1] navigating to x.com/signup")
            page.goto("https://x.com/signup", timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            # handle cookies dialog
            for sel in ["text=Accept all cookies", "text=Refuse non-essential cookies"]:
                try:
                    if page.locator(sel).count():
                        page.locator(sel).first.click(timeout=3000)
                        time.sleep(2)
                        break
                except Exception:
                    pass
            # Screenshot for debugging
            page.screenshot(path="x_step1_signup.png")
            body = page.inner_text("body")[:800]
            print(f"[1] page text: {body[:400]}")
            # Fill the "Create your account" form
            # name input
            try:
                page.fill('input[name="name"]', "Liu Daluo")
                time.sleep(1)
            except Exception as e:
                print(f"[1] name fill fail: {e}")
            try:
                page.fill('input[name="email"]', EMAIL)
                time.sleep(1)
            except Exception as e:
                print(f"[1] email fill fail: {e}")
            # DOB selects
            try:
                page.select_option('select[name="month"]', "8")
                page.select_option('select[name="day"]', "4")
                page.select_option('select[name="year"]', "1990")
                time.sleep(1)
            except Exception as e:
                print(f"[1] dob fill fail: {e}")
            page.screenshot(path="x_step1_filled.png")
            # click Next
            for sel in ['[role="button"]:has-text("Next")', 'button:has-text("Next")']:
                try:
                    if page.locator(sel).count():
                        page.locator(sel).first.click(timeout=5000)
                        time.sleep(4)
                        break
                except Exception:
                    pass
            page.screenshot(path="x_step2_after_next.png")
            body2 = page.inner_text("body")[:600]
            print(f"[1] after next: {body2[:300]}")
            save_state({"step": "signup_filled", "ts": time.time()})

        # ---- STEP 2: email verification ----
        if step in ("signup_filled", "email_otp"):
            body = page.inner_text("body")
            print(f"[2] page: {body[:300]}")
            page.screenshot(path="x_step3_email_verify.png")
            # If email OTP needed
            if OTP:
                try:
                    otp_input = page.locator('input[inputmode="numeric"]').first
                    otp_input.fill(OTP, timeout=5000)
                    time.sleep(1)
                    for sel in ['[role="button"]:has-text("Verify")', 'button:has-text("Verify")']:
                        try:
                            if page.locator(sel).count():
                                page.locator(sel).first.click(timeout=3000)
                                time.sleep(4)
                                break
                        except Exception:
                            pass
                    save_state({"step": "email_verified", "ts": time.time()})
                    print("[2] email OTP submitted")
                except Exception as e:
                    print(f"[2] otp fill fail: {e}")
            else:
                print("[2] waiting for email OTP - check if phone step offered instead")
                # check for phone step
                if "phone" in body.lower() or "enter your phone" in body.lower():
                    save_state({"step": "phone_step", "ts": time.time()})

        # ---- STEP 3: phone verification ----
        if step in ("phone_step", "email_verified"):
            body = page.inner_text("body")
            print(f"[3] page: {body[:400]}")
            page.screenshot(path="x_step4_phone.png")
            if PHONE:
                try:
                    # phone input
                    ph = page.locator('input[name="phone_number"], input[inputmode="tel"]').first
                    ph.fill(PHONE, timeout=5000)
                    time.sleep(1)
                    for sel in ['[role="button"]:has-text("Next")', 'button:has-text("Next")']:
                        try:
                            if page.locator(sel).count():
                                page.locator(sel).first.click(timeout=3000)
                                time.sleep(4)
                                break
                        except Exception:
                            pass
                    page.screenshot(path="x_step5_sms_sent.png")
                    save_state({"step": "sms_sent", "ts": time.time()})
                    print("[3] phone submitted, SMS should be sent. Need OTP from operator.")
                except Exception as e:
                    print(f"[3] phone fill fail: {e}")
                    page.screenshot(path="x_step4_phone_err.png")

        # ---- STEP 4: SMS OTP ----
        if step in ("sms_sent", "sms_otp"):
            body = page.inner_text("body")
            print(f"[4] page: {body[:300]}")
            if OTP:
                try:
                    otp_input = page.locator('input[inputmode="numeric"]').first
                    otp_input.fill(OTP, timeout=5000)
                    time.sleep(1)
                    for sel in ['[role="button"]:has-text("Verify")', 'button:has-text("Verify")']:
                        try:
                            if page.locator(sel).count():
                                page.locator(sel).first.click(timeout=3000)
                                time.sleep(4)
                                break
                        except Exception:
                            pass
                    page.screenshot(path="x_step6_sms_verified.png")
                    save_state({"step": "sms_verified", "ts": time.time()})
                    print("[4] SMS OTP submitted")
                except Exception as e:
                    print(f"[4] sms otp fill fail: {e}")
            else:
                print("[4] NEED X_OTP input to continue - rerun with otp=<code>")
                # dump state to artifact
                save_state({"step": "sms_sent", "ts": time.time()})
                sys.exit(0)

        # ---- STEP 5: password + finish ----
        if step in ("sms_verified", "finish"):
            body = page.inner_text("body")
            print(f"[5] page: {body[:300]}")
            if PASSWORD:
                try:
                    pw = page.locator('input[name="password"]').first
                    pw.fill(PASSWORD, timeout=5000)
                    time.sleep(1)
                    for sel in ['[role="button"]:has-text("Sign up")', 'button:has-text("Sign up")', '[data-testid="signup"]']:
                        try:
                            if page.locator(sel).count():
                                page.locator(sel).first.click(timeout=3000)
                                time.sleep(6)
                                break
                        except Exception:
                            pass
                    page.screenshot(path="x_step7_done.png")
                    # save cookies for later posting
                    cookies = ctx.cookies()
                    with open(COOKIE_FILE, "w") as f:
                        json.dump(cookies, f)
                    save_state({"step": "done", "ts": time.time()})
                    print("[5] registration complete, cookies saved")
                    body_final = page.inner_text("body")[:300]
                    print(f"[5] final page: {body_final}")
                except Exception as e:
                    print(f"[5] password fill fail: {e}")
            else:
                print("[5] no password set")

        browser.close()

if __name__ == "__main__":
    main()
