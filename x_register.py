#!/usr/bin/env python3
"""X (Twitter) account registration — email-first via username_or_email input.

2026-08-04 DOM 实测: x.com/signup 首页有:
  - button "Continue with phone"
  - div[role=button] "Continue with Google"
  - button "Continue with Apple"
  - input[name="username_or_email"]  (邮箱输入框, 不是按钮!)
  - input[name="password"]  (登录密码框, 注册时忽略)
  - "Continue" 按钮

正确注册路径: 在 username_or_email 填邮箱 -> 点 Continue
-> X 检测邮箱未注册 -> 进入创建账号流程 (姓名/生日/密码) -> 邮箱 OTP 或手机验证。
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

def nuke_overlays(page):
    try:
        n = page.evaluate("""() => {
          let count = 0;
          const kill = (el) => {
            if (!el || !el.style) return;
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('pointer-events', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
            count++;
          };
          const layers = document.querySelector('#layers');
          if (layers) {
            layers.querySelectorAll('[data-testid="mask"], [role="group"], [role="dialog"], [aria-modal="true"]').forEach(kill);
            layers.querySelectorAll('div').forEach(el => {
              const r = el.getBoundingClientRect();
              if (r.width >= window.innerWidth - 20 && r.height >= window.innerHeight - 20 && r.top <= 0) kill(el);
            });
          }
          return count;
        }""")
        print(f"[ov] removed {n} overlays", flush=True)
        time.sleep(1)
    except Exception as e:
        print(f"[ov] err {e}", flush=True)

def page_body(page):
    try:
        return page.inner_text("body")[:500]
    except Exception:
        return ""

from playwright.sync_api import sync_playwright

def main():
    state = load_state()
    step = state.get("step", "start")
    print(f"[cfg] email={EMAIL} otp={bool(OTP)} step={step}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()

        # ---- STEP 1: fill email in username_or_email, click Continue ----
        if step == "start":
            print("[1] open x.com/signup", flush=True)
            page.goto("https://x.com/signup", timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
            print(f"[1] page: {page_body(page)[:200]}", flush=True)
            page.screenshot(path="x_s1_home.png")
            nuke_overlays(page)
            # fill the email input (name=username_or_email)
            try:
                email_input = page.locator('input[name="username_or_email"]').first
                if email_input.count():
                    email_input.fill(EMAIL, timeout=8000)
                    time.sleep(1)
                    print(f"[1] email filled: {EMAIL}", flush=True)
                    email_input.press("Enter", timeout=5000)  # Enter = submit
                    print("[1] pressed Enter", flush=True)
                    time.sleep(6)
                    page.screenshot(path="x_s2_after_email.png")
                    print(f"[1] after: {page_body(page)[:300]}", flush=True)
                else:
                    print("[1] email input NOT found!", flush=True)
            except Exception as e:
                print(f"[1] email fill err: {e}", flush=True)
            save_state({"step": "email_next", "ts": time.time()})

        # ---- STEP 2: X response — new account form or OTP ----
        if step == "email_next":
            body = page_body(page)
            print(f"[2] page: {body[:300]}", flush=True)
            page.screenshot(path="x_s3_email_next.png")
            low = body.lower()
            if "create your account" in low or "customize your experience" in low or "name" in low and "phone" in low:
                print("[2] create-account form detected", flush=True)
                step = "create_form"
            elif "verification" in low or "code" in low or "check your email" in low or "we sent" in low:
                print("[2] OTP/verification requested", flush=True)
                step = "otp"
            elif "phone" in low and "verify" in low:
                print("[2] phone verification requested", flush=True)
                step = "phone_verify"
            else:
                print("[2] unknown state, dump:", flush=True)
                print(body[:400], flush=True)
                step = "unknown"
            save_state({"step": step, "ts": time.time()})

        # ---- STEP 3: create account form ----
        if step == "create_form":
            body = page_body(page)
            print(f"[3] create form: {body[:300]}", flush=True)
            page.screenshot(path="x_s4_create_form.png")
            nuke_overlays(page)
            # fill name
            try:
                name_input = page.locator('input[name="name"]').first
                if name_input.count():
                    name_input.fill("Liu Daluo", timeout=6000)
                    time.sleep(0.5)
                    print("[3] name filled", flush=True)
            except Exception as e:
                print(f"[3] name: {e}", flush=True)
            # DOB selects
            try:
                page.select_option('select[name="month"]', "8")
                page.select_option('select[name="day"]', "4")
                page.select_option('select[name="year"]', "1990")
                time.sleep(0.5)
                print("[3] DOB set", flush=True)
            except Exception as e:
                print(f"[3] dob: {e}", flush=True)
            page.screenshot(path="x_s5_create_filled.png")
            # click Next
            ok = click(page, ['[role="button"]:has-text("Next")', 'button:has-text("Next")', '[data-testid="nextButton"]'])
            print(f"[3] clicked Next: {ok}", flush=True)
            time.sleep(6)
            page.screenshot(path="x_s6_after_create.png")
            print(f"[3] after: {page_body(page)[:300]}", flush=True)
            save_state({"step": "create_next", "ts": time.time()})

        # ---- STEP 4: post-create (email OTP / phone / code) ----
        if step == "create_next":
            body = page_body(page)
            print(f"[4] page: {body[:300]}", flush=True)
            page.screenshot(path="x_s7_create_next.png")
            low = body.lower()
            if OTP:
                try:
                    otp_inputs = page.locator('input[inputmode="numeric"], input[autocomplete="one-time-code"]')
                    n = otp_inputs.count()
                    print(f"[4] otp inputs: {n}", flush=True)
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
                        print(f"[4] clicked verify: {ok}", flush=True)
                        time.sleep(6)
                        page.screenshot(path="x_s8_otp_done.png")
                        print(f"[4] after otp: {page_body(page)[:250]}", flush=True)
                        step = "password"
                        save_state({"step": step, "ts": time.time()})
                    else:
                        print("[4] no OTP input", flush=True)
                except Exception as e:
                    print(f"[4] otp err: {e}", flush=True)
            else:
                print("[4] NEED OTP — rerun with otp=<code>", flush=True)

        # ---- STEP 5: password / username ----
        if step == "password":
            body = page_body(page)
            print(f"[5] page: {body[:300]}", flush=True)
            page.screenshot(path="x_s9_password.png")
            nuke_overlays(page)
            try:
                pw = page.locator('input[type="password"], input[name="password"]').first
                if pw.count():
                    pw.fill(PASSWORD, timeout=6000)
                    time.sleep(0.5)
                    print("[5] password filled", flush=True)
            except Exception as e:
                print(f"[5] pw: {e}", flush=True)
            try:
                un = page.locator('input[name="username"]').first
                if un.count():
                    un.fill(USERNAME, timeout=6000)
                    time.sleep(0.5)
                    print("[5] username filled", flush=True)
            except Exception as e:
                print(f"[5] user: {e}", flush=True)
            page.screenshot(path="x_s10_password_filled.png")
            ok = click(page, ['[role="button"]:has-text("Sign up")', '[data-testid="signup"]', 'button:has-text("Sign up")'])
            print(f"[5] clicked signup: {ok}", flush=True)
            time.sleep(8)
            page.screenshot(path="x_s11_final.png")
            print(f"[5] final: {page_body(page)[:250]}", flush=True)
            try:
                cookies = ctx.cookies()
                with open(COOKIE_FILE, "w") as f:
                    json.dump(cookies, f)
                print(f"[5] cookies saved ({len(cookies)})", flush=True)
                save_state({"step": "done", "ts": time.time()})
            except Exception as e:
                print(f"[5] cookie err: {e}", flush=True)

        browser.close()
        print(f"[end] step={step}", flush=True)

if __name__ == "__main__":
    main()
