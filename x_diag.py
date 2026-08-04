#!/usr/bin/env python3
"""Diagnose x.com/signup page structure — dump clickable elements & inputs."""
import json, os, sys, time

from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()
        page.goto("https://x.com/signup", timeout=60000, wait_until="domcontentloaded")
        time.sleep(6)

        # dump all buttons / roles / inputs with their text & data-testid
        info = page.evaluate("""() => {
          const out = [];
          const els = document.querySelectorAll('button, [role="button"], a, input');
          els.forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            out.push({
              tag: el.tagName,
              role: el.getAttribute('role'),
              testid: el.getAttribute('data-testid'),
              type: el.getAttribute('type'),
              name: el.getAttribute('name'),
              placeholder: el.getAttribute('placeholder'),
              text: (el.innerText || el.textContent || el.value || '').trim().slice(0, 60),
              visible: r.width > 0 && r.height > 0
            });
          });
          return JSON.stringify(out, null, 1);
        }""")
        print("=== ALL VISIBLE ELEMENTS ===")
        print(info)
        page.screenshot(path="x_diag_home.png")
        browser.close()

if __name__ == "__main__":
    main()
