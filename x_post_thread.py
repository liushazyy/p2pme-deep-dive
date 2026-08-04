#!/usr/bin/env python3
"""Post a Twitter thread using saved cookies — runs on GitHub Actions overseas runner.

Usage: python x_post_thread.py <thread-file> [extra-tags]
Thread file: JSON array of tweet strings, or plain text with TWEET separators.
Uses x_cookies.json saved during registration. If cookies expired, falls back to login.
"""
import json, os, sys, time

TAGS = os.environ.get("X_TAGS", "")  # e.g. "@meleemarkets"
POST_FILE = os.environ.get("X_POST_FILE", "thread.json")
COOKIE_FILE = "x_cookies.json"

from playwright.sync_api import sync_playwright

def load_thread(path):
    if path.endswith(".json"):
        with open(path) as f:
            return json.load(f)
    with open(path) as f:
        txt = f.read().strip()
    # split by --- separator
    return [t.strip() for t in txt.split("\n---\n") if t.strip()]

def main():
    tweets = load_thread(POST_FILE)
    print(f"[post] {len(tweets)} tweets to post", flush=True)
    # append tags to first tweet if not present
    if TAGS and TAGS not in tweets[0]:
        tweets[0] = tweets[0] + "\n\n" + TAGS
    print(f"[post] first tweet: {tweets[0][:120]}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
        # load saved cookies
        try:
            with open(COOKIE_FILE) as f:
                cookies = json.load(f)
            ctx.add_cookies(cookies)
            print(f"[post] loaded {len(cookies)} cookies", flush=True)
        except Exception as e:
            print(f"[post] no cookies: {e}", flush=True)

        page = ctx.new_page()
        page.goto("https://x.com/home", timeout=60000, wait_until="domcontentloaded")
        time.sleep(6)
        body = page.inner_text("body")[:300]
        print(f"[post] home: {body[:200]}", flush=True)
        page.screenshot(path="x_post_home.png")

        # Check if logged in: look for composer or login form
        logged_in = "Login" not in body[:100] and "Sign up" not in body[:100]
        print(f"[post] logged_in={logged_in}", flush=True)
        if not logged_in:
            print("[post] NOT logged in — need re-auth", flush=True)
            sys.exit(2)

        # open composer (tweet box)
        # click the "Post" textarea
        try:
            composer = page.locator('[data-testid="tweetTextarea_0"], [contenteditable="true"]').first
            composer.click(timeout=10000)
            time.sleep(2)
        except Exception as e:
            print(f"[post] composer open: {e}", flush=True)

        # post each tweet: type -> Next -> type -> Post/Next
        for i, tw in enumerate(tweets):
            print(f"[post] tweet {i+1}/{len(tweets)}: {tw[:80]}", flush=True)
            try:
                # find the active composer (last one)
                areas = page.locator('[contenteditable="true"]')
                n = areas.count()
                target = areas.nth(n - 1)
                target.click(timeout=8000)
                time.sleep(1)
                # select all then type
                page.keyboard.press("Control+a")
                page.keyboard.type(tw, delay=5)
                time.sleep(1)
                page.screenshot(path=f"x_post_t{i+1}_typed.png")
            except Exception as e:
                print(f"[post] type err: {e}", flush=True)
                continue

            # submit: for last tweet, button is "Post"/"Tweet"; for others "Next"
            submitted = False
            if i == len(tweets) - 1:
                for sel in ['[data-testid="tweetButton"]', '[role="button"]:has-text("Post")', '[role="button"]:has-text("Tweet")']:
                    try:
                        btn = page.locator(sel)
                        if btn.count() and btn.first.is_visible():
                            btn.first.click(timeout=5000)
                            submitted = True
                            break
                    except Exception:
                        pass
            else:
                for sel in ['[role="button"]:has-text("Next")', '[data-testid="tweetButtonInline"]']:
                    try:
                        btn = page.locator(sel)
                        if btn.count() and btn.first.is_visible():
                            btn.first.click(timeout=5000)
                            submitted = True
                            time.sleep(3)
                            break
                    except Exception:
                        pass
            print(f"[post] tweet {i+1} submitted={submitted}", flush=True)
            time.sleep(3)

        page.screenshot(path="x_post_final.png")
        # get the thread URL
        url = page.url
        print(f"[post] FINAL URL: {url}", flush=True)
        body_f = page.inner_text("body")[:200]
        print(f"[post] final: {body_f}", flush=True)
        browser.close()

if __name__ == "__main__":
    main()
