#!/usr/bin/env python3
"""X login on GitHub Actions runner — saves cookies for local reuse.
If verification (SMS/email) is required, it dumps the state and waits for OTP input via dispatch.
"""
import json, os, sys, time

from playwright.sync_api import sync_playwright

USER = os.environ.get("X_USER", "")
PASS = os.environ.get("X_PASS", "")
OTP = os.environ.get("OTP", "")

def save_cookies(context):
    cookies = context.cookies()
    with open("x_cookies.json", "w") as f:
        json.dump(cookies, f)
    print(f"[cookies] saved {len(cookies)} cookies")
    return cookies

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        page = ctx.new_page()

        print("[1] open x.com/login")
        page.goto("https://x.com/login", timeout=90000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # Fill username/email
        try:
            page.fill('input[name="username_or_email"]', USER, timeout=15000)
            page.wait_for_timeout(1000)
            page.fill('input[name="password"]', PASS, timeout=15000)
            page.wait_for_timeout(1000)
            print("[2] filled credentials")
        except Exception as e:
            print(f"[2] fill error: {e}")
            page.screenshot(path="x_step2.png")

        # Press Enter / click login
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(8000)
            print("[3] pressed Enter")
        except Exception as e:
            print(f"[3] enter error: {e}")

        page.screenshot(path="x_after_login.png")
        url = page.url
        print(f"[4] URL: {url}")
        text = page.inner_text("body")[:400]
        print(f"[4] text: {text}")

        # Check if we're logged in (home page)
        if "home" in url or "看看正在发生什么" not in text and "正在发生" not in text and "signup" not in url and "onboarding" not in url:
            save_cookies(ctx)
            print("[5] LOGIN SUCCESS (no verification needed)")
            return

        # Onboarding / verification screen
        if "onboarding" in url or "请从下方选择一项" in text or "看看正在发生什么" in text:
            print("[5] verification required - trying phone continue")
            try:
                btn = page.get_by_role("button", name="使用手机继续")
                if btn.count() == 0:
                    btn = page.get_by_role("button", name="Continue with phone")
                btn.first.click(timeout=10000)
                page.wait_for_timeout(5000)
                print("[6] clicked phone continue")
            except Exception as e:
                print(f"[6] phone continue error: {e}")

            page.screenshot(path="x_verify.png")
            url2 = page.url
            text2 = page.inner_text("body")[:500]
            print(f"[7] URL: {url2}")
            print(f"[7] text: {text2}")

            # Phone number screen — fill +86 and phone
            if "signup_phone" in url2 or "phone" in url2.lower() or "电话号码" in text2:
                # country picker -> China
                try:
                    picker = page.locator(".jf-phone-country-picker, .jf-phone-country-button").first
                    picker.click(timeout=8000)
                    page.wait_for_timeout(2000)
                    search = page.locator('input[placeholder="Search"]').first
                    search.fill("China", timeout=8000)
                    page.wait_for_timeout(2000)
                    china = page.locator('text=China+86, text=🇨🇳China+86').first
                    china.click(timeout=8000)
                    page.wait_for_timeout(2000)
                    print("[8] country -> China +86")
                except Exception as e:
                    print(f"[8] country pick error: {e}")

                try:
                    phone_input = page.locator('input[name="phone"]').first
                    phone_input.fill(USER, timeout=8000)
                    page.wait_for_timeout(1000)
                    print(f"[9] phone filled: {USER}")
                    page.screenshot(path="x_phone_filled.png")
                    # click Continue
                    cont = page.get_by_role("button", name="继续").last
                    cont.click(timeout=10000)
                    page.wait_for_timeout(8000)
                    print("[10] clicked continue")
                except Exception as e:
                    print(f"[10] phone fill error: {e}")

                page.screenshot(path="x_otp_screen.png")
                text3 = page.inner_text("body")[:500]
                print(f"[11] text: {text3}")
                if OTP:
                    try:
                        otp_input = page.locator('input[inputmode="numeric"], input[type="tel"], input[name="verification"]').first
                        otp_input.fill(OTP, timeout=8000)
                        page.wait_for_timeout(1000)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(8000)
                        print("[12] OTP submitted")
                    except Exception as e:
                        print(f"[12] OTP error: {e}")
                else:
                    print("[OTP_REQUIRED] X sent SMS to phone - re-dispatch with otp input")

        page.screenshot(path="x_final.png")
        save_cookies(ctx)
        print(f"[FINAL] URL: {page.url}")

if __name__ == "__main__":
    main()
