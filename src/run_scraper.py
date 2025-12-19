from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from pathlib import Path

from src.coppel_parser import parse_pdp, parse_plp_products
from src.coppel_playwright import PlaywrightClient
from src.mailer import send_email
from src.settings import get_settings
from src.storage import save_csv, save_xlsx
from src.utils import (
    LOGGER,
    clean_text,
    ensure_dir,
    utc_iso,
    write_json,
)


def _read_urls(file_path: Path) -> list[str]:
    if not file_path.exists():
        LOGGER.error("URLs file not found: %s", file_path)
        return []
    urls = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()]
    return [url for url in urls if url and not url.startswith("#")]


def _base_row(settings, mode: str, source_url: str) -> dict:
    return {
        "timestamp_utc": utc_iso(),
        "mode": mode,
        "source_url": source_url,
        "final_url": "",
        "product_url": "",
        "title": "",
        "price_regular": "",
        "price_promo": "",
        "currency": "MXN",
        "availability": "unknown",
        "stock_text": "",
        "seller": "",
        "brand": "",
        "model": "",
        "sku": "",
        "category": "",
        "description_short": "",
        "description_full": "",
        "description_full_path": "",
        "images": "",
        "rating": "",
        "reviews_count": "",
        "http_status": "",
        "page_type_detected": "unknown",
        "status": "",
        "error": "",
        "attempts": 0,
        "elapsed_sec": 0.0,
    }


def _summarize(rows: list[dict]) -> dict:
    summary = {"pdp": {}, "plp": {}, "total": {}}
    for row in rows:
        mode = row.get("mode", "unknown")
        status = row.get("status", "unknown")
        summary.setdefault(mode, {})
        summary[mode][status] = summary[mode].get(status, 0) + 1
        summary["total"][status] = summary["total"].get(status, 0) + 1
    return summary


def _should_stop(start_time: float, max_runtime_sec: int) -> bool:
    if max_runtime_sec <= 0:
        return False
    return (time.time() - start_time) > max_runtime_sec


def _retry_delay(attempt: int) -> float:
    base = 2 ** attempt
    return min(15.0, base + (0.5 * attempt))


def _sleep_range(settings) -> float:
    return random.uniform(settings.min_sleep_sec, settings.max_sleep_sec)


async def run_pdp(settings, client: PlaywrightClient, urls: list[str], debug_dir: Path) -> list[dict]:
    rows = []
    start_time = time.time()
    for url in urls:
        row = _base_row(settings, "pdp", url)
        start = time.time()
        for attempt in range(1, settings.max_retries_per_url + 1):
            row["attempts"] = attempt
            LOGGER.info("PDP start url=%s attempt=%d", url, attempt)
            page = None
            try:
                page = await client.new_page()
                final_url, status = await client.open_page(page, url)
                row["final_url"] = final_url
                row["product_url"] = final_url
                row["http_status"] = status or ""
                if settings.enable_stealth:
                    await page.mouse.move(200, 200)
                    await page.wait_for_timeout(500)
                await client.handle_cookie_banner(page)
                blocked = await client.detect_block(page)
                row["page_type_detected"] = "blocked" if blocked else "pdp"
                if blocked:
                    row["status"] = "BLOCK"
                    row["error"] = "Blocked by WAF/CDN"
                    await client.take_debug(page, url, settings.debug_save_html, settings.debug_save_screenshot)
                else:
                    html = await page.content()
                    await client.dump_html(page, url)
                    data = parse_pdp(html, final_url)
                    row.update(data)
                    row["status"] = "OK"
                await page.close()
                break
            except Exception as exc:
                row["status"] = "FAIL"
                row["error"] = clean_text(str(exc))[:200]
                LOGGER.info("PDP error url=%s attempt=%d error=%s", url, attempt, row["error"])
                if page:
                    try:
                        await client.take_debug(page, url, settings.debug_save_html, settings.debug_save_screenshot)
                    except Exception:
                        LOGGER.info("Failed to capture debug for %s", url)
                if attempt < settings.max_retries_per_url:
                    delay = _retry_delay(attempt)
                    LOGGER.info("Retrying %s in %.2f sec", url, delay)
                    await asyncio.sleep(delay)
                else:
                    row["status"] = "RETRY_EXHAUSTED"
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
        row["elapsed_sec"] = round(time.time() - start, 2)
        rows.append(row)
        LOGGER.info("PDP done url=%s status=%s elapsed=%.2f", url, row["status"], row["elapsed_sec"])
        await asyncio.sleep(_sleep_range(settings))
        if _should_stop(start_time, settings.max_runtime_sec):
            LOGGER.info("Max runtime reached. Stopping.")
            break
    return rows


async def _find_next_button(page) -> object | None:
    candidates = page.locator(
        "xpath=//a[contains(., 'Siguiente') or contains(., 'Next') or "
        "contains(@aria-label, 'Siguiente') or contains(@aria-label, 'Next')]"
    )
    if await candidates.count() > 0:
        return candidates.first
    buttons = page.locator(
        "xpath=//button[contains(., 'Siguiente') or contains(., 'Next') or "
        "contains(@aria-label, 'Siguiente') or contains(@aria-label, 'Next')]"
    )
    if await buttons.count() > 0:
        return buttons.first
    return None


async def run_plp(settings, client: PlaywrightClient, plp_url: str, debug_dir: Path) -> list[dict]:
    rows = []
    seen = set()
    start_time = time.time()
    for page_index in range(1, settings.max_pages + 1):
        if _should_stop(start_time, settings.max_runtime_sec):
            LOGGER.info("Max runtime reached. Stopping.")
            break
        row = _base_row(settings, "plp", plp_url)
        LOGGER.info("PLP page=%d url=%s", page_index, plp_url)
        page = None
        try:
            page = await client.new_page()
            final_url, status = await client.open_page(page, plp_url)
            row["final_url"] = final_url
            row["http_status"] = status or ""
            if settings.enable_stealth:
                await page.mouse.move(150, 180)
                await page.wait_for_timeout(500)
            await client.handle_cookie_banner(page)
            if await client.detect_block(page):
                row["status"] = "BLOCK"
                row["page_type_detected"] = "blocked"
                row["error"] = "Blocked by WAF/CDN"
                await client.take_debug(page, plp_url, settings.debug_save_html, settings.debug_save_screenshot)
                rows.append(row)
                break
            await client.dump_html(page, f"{plp_url}_page_{page_index}")
            html = await page.content()
            products = parse_plp_products(html, plp_url)
            row["page_type_detected"] = "plp"
            row["status"] = "OK"
            rows.append(row)
            for product in products:
                product_url = product.get("product_url", "")
                if product_url and product_url in seen:
                    continue
                seen.add(product_url)
                product_row = _base_row(settings, "plp", plp_url)
                product_row.update(product)
                product_row["final_url"] = final_url
                product_row["product_url"] = product_url
                product_row["status"] = "OK"
                product_row["page_type_detected"] = "plp"
                rows.append(product_row)
            next_button = await _find_next_button(page)
            if not next_button or not await next_button.is_visible():
                break
            if not await next_button.is_enabled():
                break
            token = await page.locator("css=a").first.get_attribute("href") or ""
            await next_button.scroll_into_view_if_needed()
            await next_button.click()
            try:
                await page.wait_for_timeout(1000)
                await page.wait_for_function(
                    "token => document.querySelector('a')?.getAttribute('href') !== token",
                    token,
                    timeout=settings.nav_timeout_ms,
                )
            except Exception:
                LOGGER.info("Page token did not change, trying to click via JS.")
                await page.evaluate("element => element.click()", next_button)
                await page.wait_for_timeout(1000)
            next_url = page.url
            await page.close()
            await asyncio.sleep(_sleep_range(settings))
            plp_url = next_url
        except Exception as exc:
            row["status"] = "FAIL"
            row["error"] = clean_text(str(exc))[:200]
            rows.append(row)
            if page:
                try:
                    await client.take_debug(page, plp_url, settings.debug_save_html, settings.debug_save_screenshot)
                except Exception:
                    LOGGER.info("Failed to capture debug for PLP")
            break
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
    return rows


async def main() -> int:
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    ensure_dir(output_dir)
    debug_dir = output_dir / "debug"
    ensure_dir(debug_dir)
    log_path = output_dir / "run.log"

    from src.utils import setup_logging

    setup_logging(log_path)
    LOGGER.info("Starting scraper with mode=%s", settings.mode)
    LOGGER.info(
        "Config max_urls=%s max_pages=%s headless=%s retries=%s stealth=%s persistent=%s browser=%s",
        settings.max_urls,
        settings.max_pages,
        settings.headless,
        settings.max_retries_per_url,
        settings.enable_stealth,
        settings.persistent_context,
        settings.browser,
    )
    rows = []

    urls = []
    if settings.mode == "pdp":
        urls = _read_urls(Path(settings.urls_file))
        if settings.max_urls > 0:
            urls = urls[: settings.max_urls]
        LOGGER.info("Loaded %d URLs", len(urls))
    else:
        LOGGER.info("PLP URL: %s", settings.plp_url)

    if settings.persistent_context:
        ensure_dir(Path(settings.persistent_context_dir))
    client = PlaywrightClient(settings, debug_dir)
    await client.start()
    await client.warmup("https://www.coppel.com/")

    try:
        if settings.mode == "pdp":
            rows = await run_pdp(settings, client, urls, debug_dir)
        elif settings.mode == "plp":
            if not settings.plp_url:
                LOGGER.error("PLP_URL is required for PLP mode")
            else:
                rows = await run_plp(settings, client, settings.plp_url, debug_dir)
        else:
            LOGGER.error("Unknown MODE: %s", settings.mode)
    finally:
        await client.close()

    results_csv = output_dir / "results.csv"
    results_xlsx = output_dir / "results.xlsx"
    summary_path = output_dir / "summary.json"

    save_csv(rows, results_csv)
    save_xlsx(rows, results_xlsx)
    write_json(summary_path, _summarize(rows))

    LOGGER.info("Saved results to %s", results_csv)

    body = {
        "total_rows": len(rows),
        "summary": _summarize(rows),
    }
    email_body = json.dumps(body, ensure_ascii=False, indent=2)
    attachments = [results_xlsx, results_csv, log_path, summary_path]
    send_email(settings, settings.email_subject, email_body, attachments)

    ok_count = sum(1 for row in rows if row.get("status") == "OK")
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
