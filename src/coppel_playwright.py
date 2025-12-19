from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from src.settings import Settings
from src.utils import clean_text, hash_key, parse_headers_json


LOGGER = logging.getLogger("coppel_scraper")


BLOCK_KEYWORDS = [
    "access denied",
    "request blocked",
    "temporarily unavailable",
    "captcha",
    "are you human",
    "akamai",
    "cloudflare",
]


class PlaywrightClient:
    def __init__(self, settings: Settings, debug_dir: Path) -> None:
        self.settings = settings
        self.debug_dir = debug_dir
        self.playwright = sync_playwright().start()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def start(self) -> None:
        launch_args = []
        if self.settings.disable_automation_flags:
            launch_args.extend(
                [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ]
            )

        browser_type = self._browser_type()
        context_kwargs = {
            "user_agent": self.settings.user_agent,
            "locale": self.settings.locale,
            "timezone_id": self.settings.timezone,
            "viewport": {"width": 1366, "height": 768},
            "java_script_enabled": True,
        }
        if self.settings.persistent_context:
            self.context = browser_type.launch_persistent_context(
                user_data_dir=self.settings.persistent_context_dir,
                headless=self.settings.headless,
                slow_mo=self.settings.slow_mo_ms or None,
                args=launch_args if self.settings.browser == "chromium" else [],
                **context_kwargs,
            )
        else:
            self.browser = browser_type.launch(
                headless=self.settings.headless,
                slow_mo=self.settings.slow_mo_ms or None,
                args=launch_args if self.settings.browser == "chromium" else [],
            )
            self.context = self.browser.new_context(**context_kwargs)
        self.context.set_default_timeout(self.settings.wait_selector_ms)
        self.context.set_default_navigation_timeout(self.settings.nav_timeout_ms)
        headers = {"Accept-Language": self.settings.locale}
        headers.update(parse_headers_json(self.settings.extra_headers_json))
        self.context.set_extra_http_headers(headers)
        if self.settings.enable_stealth:
            self.context.add_init_script(self._stealth_script())
        if self.settings.block_images:
            self.context.route(
                "**/*",
                lambda route, request: route.abort()
                if request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )

    def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        return self.context.new_page()

    def open_page(self, page: Page, url: str) -> tuple[str, int | None]:
        status = None
        for wait_until in ("domcontentloaded", "load"):
            try:
                response = page.goto(url, wait_until=wait_until)
                status = response.status if response else None
                break
            except Exception as exc:
                LOGGER.info("Navigation attempt failed (%s): %s", wait_until, exc)
        try:
            page.wait_for_load_state("networkidle", timeout=self.settings.nav_timeout_ms)
        except Exception as exc:
            LOGGER.info("Network idle timeout: %s", exc)
        return page.url, status

    def detect_block(self, page: Page) -> bool:
        try:
            content = clean_text(page.content().lower())
        except Exception:
            return False
        return any(keyword in content for keyword in BLOCK_KEYWORDS)

    def take_debug(self, page: Page, key: str, save_html: bool, save_shot: bool) -> None:
        if not save_html and not save_shot:
            return
        digest = hash_key(key)
        if save_html:
            html_path = self.debug_dir / f"html_{digest}.html"
            html_path.write_text(page.content(), encoding="utf-8")
        if save_shot:
            shot_path = self.debug_dir / f"shot_{digest}.png"
            page.screenshot(path=str(shot_path), full_page=True)

    def dump_html(self, page: Page, key: str) -> None:
        if not self.settings.dump_html:
            return
        digest = hash_key(key)
        html_path = self.debug_dir / f"dump_{digest}.html"
        html_path.write_text(page.content(), encoding="utf-8")

    def close(self) -> None:
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        self.playwright.stop()

    def warmup(self, url: str) -> None:
        try:
            page = self.new_page()
            page.goto(url, wait_until="domcontentloaded")
            self.handle_cookie_banner(page)
            page.wait_for_timeout(1000)
            page.close()
        except Exception as exc:
            LOGGER.info("Warmup failed: %s", exc)

    def _stealth_script(self) -> str:
        return """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['es-MX', 'es', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""

    def _browser_type(self):
        if self.settings.browser == "firefox":
            return self.playwright.firefox
        if self.settings.browser == "webkit":
            return self.playwright.webkit
        return self.playwright.chromium

    def handle_cookie_banner(self, page: Page) -> None:
        try:
            button = page.locator(
                "xpath=//button[contains(., 'Aceptar') or contains(., 'Acepto') or "
                "contains(., 'Aceptar todo') or contains(., 'Allow all')]"
            )
            if button.count() > 0 and button.first.is_visible():
                button.first.click()
                page.wait_for_timeout(500)
        except Exception:
            return
