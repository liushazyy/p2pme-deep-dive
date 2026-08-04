#!/usr/bin/env python3
"""X (Twitter) account registration — phone-first flow (current X signup page).

2026-08-04 实测: x.com/signup 首页 = "See what's happening / Select an option below:
Continue with phone / Continue with Google / Continue with Apple / or: Email or username [Continue]"
没有 name/email 表单，必须先从入口按钮进。

Flow (phone-first):
  signup 页 -> 点 "Continue with phone" -> 选国家码 + 输手机号 -> Next
  -> X 发 SMS OTP -> 用户提供 OTP -> 填 OTP -> Verify
  -> 设置名字/用户名/密码 -> 完成 (存 cookies)
"""
import json, os, sys, time

EMAIL = os.environ.get("X_EMAIL", "")
USERNAME = os.environ.get("X_USERNAME", "")
PASSWORD = os.environ.get("X_PASSWORD", "")
PHONE = os.environ.get("X_PHONE", "")          # e.g. +8619137767895
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
    print(f"[state] step={s.get('step')} saved", flush=True)

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

from playwright.sync_api import sync_playwright

def main():
    state = load_state()
    step = state.get("step", "start")
    print(f"[cfg] phone={PHONE[-4:] if PHONE else '?'} user={USERNAME} otp_given={bool(OTP)} resume={RESUME} step={step}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()

        # ---- STEP 1: signup page -> Continue with phone ----
        if step == "start":
            print("[1] open x.com/signup", flush=True)
            page.goto("https://x.com/signup", timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
            page.screenshot(path="x_s1_home.png")
            body = page.inner_text("body")[:500]
            print(f"[1] page: {body[:300]}", flush=True)
            # click Continue with phone
            ok = click(page, ['[role="button"]:has-text("Continue with phone")', 'button:has-text("Continue with phone")'])
            print(f"[1] clicked phone entry: {ok}", flush=True)
            time.sleep(4)
            page.screenshot(path="x_s2_phone_entry.png")
            save_state({"step": "phone_entry", "ts": time.time()})

        # ---- STEP 2: phone number form ----
        if step == "phone_entry":
            body = page.inner_text("body")[:400]
            print(f"[2] page: {body[:250]}", flush=True)
            # country code dropdown: X uses a select with country codes
            # phone input
            filled = False
            try:
                # find visible text/tel input
                inputs = page.locator('input:visible')
                n = inputs.count()
                print(f"[2] visible inputs: {n}", flush=True)
                for i in range(n):
                    ph = inputs.nth(i).get_attribute("placeholder") or ""
                    inp_type = inputs.nth(i).get_attribute("inputmode") or inputs.nth(i).get_attribute("type") or ""
                    print(f"  [{i}] type={inp_type} ph={ph}", flush=True)
                # X phone input has name="phone_number" or inputmode=tel
                ph_input = page.locator('input[inputmode="tel"], input[name="phone_number"]').first
                if ph_input.count():
                    digits = PHONE.replace("+", "").replace(" ", "")
                    ph_input.fill(digits, timeout=8000)
                    time.sleep(1)
                    filled = True
            except Exception as e:
                print(f"[2] phone fill: {e}", flush=True)
            page.screenshot(path="x_s3_phone_filled.png")
            if filled:
                ok = click(page, ['[role="button"]:has-text("Next")', 'button:has-text("Next")'])
                print(f"[2] clicked Next: {ok}", flush=True)
                time.sleep(5)
                page.screenshot(path="x_s4_after_next.png")
                body2 = page.inner_text("body")[:400]
                print(f"[2] after: {body2[:250]}", flush=True)
                save_state({"step": "sms_sent", "ts": time.time()})
                print("[2] phone submitted — SMS sent. Rerun with otp=<code>", flush=True)

        # ---- STEP 3: SMS OTP ----
        if step == "sms_sent":
            body = page.inner_text("body")[:400]
            print(f"[3] page: {body[:250]}", flush=True)
            if OTP:
                try:
                    # numeric OTP input(s)
                    otp_inputs = page.locator('input[inputmode="numeric"], input[autocomplete="one-time-code"]')
                    n = otp_inputs.count()
                    print(f"[3] otp inputs: {n}", flush=True)
                    if n >= 1:
                        # fill each char in sequence if multiple boxes
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
                        page.screenshot(path="x_s5_otp_done.png")
                        body3 = page.inner_text("body")[:400]
                        print(f"[3] after otp: {body3[:250]}", flush=True)
                        save_state({"step": "details", "ts": time.time()})
                    else:
                        print("[3] no OTP input found", flush=True)
                except Exception as e:
                    print(f"[3] otp fill err: {e}", flush=True)
            else:
                print("[3] NEED X_OTP — rerun with otp=<code>", flush=True)
                page.screenshot(path="x_s5_wait_otp.png")

        # ---- STEP 4: name/password/details ----
        if step == "details":
            body = page.inner_text("body")[:500]
            print(f"[4] page: {body[:300]}", flush=True)
            # fill name
            try:
                name_input = page.locator('input[name="name"], input[autocomplete="name"]').first
                if name_input.count():
                    name_input.fill("Liu Daluo", timeout=6000)
                    time.sleep(0.5)
            except Exception:
                pass
            # password
            try:
                pw = page.locator('input[type="password"], input[name="password"]').first
                if pw.count():
                    pw.fill(PASSWORD, timeout=6000)
                    time.sleep(0.5)
            except Exception:
                pass
            # username
            try:
                un = page.locator('input[name="username"], input[autocomplete="username"]').first
                if un.count():
                    un.fill(USERNAME, timeout=6000)
                    time.sleep(0.5)
            except Exception:
                pass
            page.screenshot(path="x_s6_details_filled.png")
            ok = click(page, ['[role="button"]:has-text("Sign up")', 'button:has-text("Sign up")', '[data-testid="signup"]'])
            print(f"[4] clicked signup: {ok}", flush=True)
            time.sleep(8)
            page.screenshot(path="x_s7_final.png")
            body4 = page.inner_text("body")[:400]
            print(f"[4] final: {body4[:250]}", flush=True)
            # save cookies regardless
            try:
                cookies = ctx.cookies()
                with open(COOKIE_FILE, "w") as f:
                    json.dump(cookies, f)
                save_state({"step": "done", "ts": time.time()})
                print(f"[4] cookies saved ({len(cookies)})", flush=True)
            except Exception as e:
                print(f"[4] cookie save err: {e}", flush=True)

        browser.close()

if __name__ == "__main__":
    main()
