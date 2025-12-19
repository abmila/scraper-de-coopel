from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from src.utils import clean_text, parse_price


LOGGER = logging.getLogger("coppel_scraper")


def _get_text(el) -> str:
    if not el:
        return ""
    return clean_text(el.get_text(" "))


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = _get_text(el)
            if text:
                return text
    return ""


def _meta_content(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        el = soup.select_one(selector)
        if el and el.get("content"):
            return clean_text(el["content"])
    return ""


def extract_title(soup: BeautifulSoup) -> str:
    title = _first_text(soup, ["h1", "[data-testid='product-title']", ".product-title"])
    if title:
        return title
    return _meta_content(soup, ["meta[property='og:title']", "meta[name='title']"])


def extract_prices(soup: BeautifulSoup) -> tuple[float | None, float | None]:
    price_candidates = []
    for selector in [
        "[data-testid='price']",
        ".price",
        ".product-price",
        "meta[property='product:price:amount']",
    ]:
        el = soup.select_one(selector)
        if not el:
            continue
        if el.name == "meta":
            price_candidates.append(el.get("content", ""))
        else:
            price_candidates.append(_get_text(el))
    regular = promo = None
    if price_candidates:
        regular = parse_price(price_candidates[0])
    promo_text = _first_text(soup, [".price--promo", ".price-promo", "[data-testid='price-promo']"])
    promo = parse_price(promo_text) if promo_text else None
    if promo is None and len(price_candidates) > 1:
        promo = parse_price(price_candidates[1])
    return regular, promo


def extract_brand_model_sku(soup: BeautifulSoup) -> tuple[str, str, str]:
    brand = _first_text(soup, ["[itemprop='brand']", ".product-brand", "[data-testid='brand']"])
    model = _first_text(soup, ["[itemprop='model']", ".product-model", "[data-testid='model']"])
    sku = _first_text(soup, ["[itemprop='sku']", ".product-sku", "[data-testid='sku']"])
    if not sku:
        sku = _meta_content(soup, ["meta[itemprop='sku']"])
    return brand, model, sku


def extract_description(soup: BeautifulSoup) -> tuple[str, str]:
    short_desc = _first_text(soup, [
        "[data-testid='short-description']",
        ".product-short-description",
        "meta[name='description']",
    ])
    full_desc = _first_text(soup, [
        "[data-testid='description']",
        ".product-description",
        "#descripcion",
    ])
    return short_desc[:2000], full_desc[:8000]


def extract_images(soup: BeautifulSoup) -> list[str]:
    urls = []
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src")
        if src and src.startswith("http"):
            urls.append(src)
    if not urls:
        json_ld = _extract_json_ld(soup)
        if json_ld and isinstance(json_ld.get("image"), list):
            urls = json_ld["image"]
        elif json_ld and isinstance(json_ld.get("image"), str):
            urls = [json_ld["image"]]
    return list(dict.fromkeys(urls))


def _extract_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return None


def parse_pdp(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    regular, promo = extract_prices(soup)
    brand, model, sku = extract_brand_model_sku(soup)
    short_desc, full_desc = extract_description(soup)
    images = extract_images(soup)
    availability = _first_text(soup, ["[data-testid='availability']", ".availability"])
    rating = _first_text(soup, ["[data-testid='rating']", ".rating"])
    reviews = _first_text(soup, ["[data-testid='reviews']", ".reviews"])
    return {
        "title": title,
        "price_regular": regular,
        "price_promo": promo,
        "currency": "MXN",
        "availability": availability or "unknown",
        "stock_text": availability,
        "seller": _first_text(soup, ["[data-testid='seller']", ".seller"]),
        "brand": brand,
        "model": model,
        "sku": sku,
        "category": _first_text(soup, [".breadcrumb", "[data-testid='breadcrumb']"]),
        "description_short": short_desc,
        "description_full": full_desc,
        "images": json.dumps(images, ensure_ascii=False),
        "rating": rating,
        "reviews_count": re.sub(r"\D", "", reviews) if reviews else "",
        "product_url": url,
    }


def parse_plp_products(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    products: list[dict[str, Any]] = []

    json_ld = _extract_item_list(soup)
    if json_ld:
        for item in json_ld:
            products.append(
                {
                    "title": clean_text(item.get("name", "")),
                    "price_regular": parse_price(str(item.get("offers", {}).get("price", ""))),
                    "price_promo": None,
                    "currency": item.get("offers", {}).get("priceCurrency", "MXN"),
                    "product_url": item.get("url", ""),
                }
            )

    card_selectors = [
        "[data-testid*='product-card']",
        ".product-card",
        ".product-item",
        "li.product",
    ]

    cards = []
    for selector in card_selectors:
        found = soup.select(selector)
        if found:
            cards = found
            break

    for card in cards:
        link = card.find("a", href=True)
        title = _get_text(card.find(["h2", "h3"])) or _get_text(link)
        regular, promo = extract_prices(BeautifulSoup(str(card), "lxml"))
        products.append(
            {
                "title": title,
                "price_regular": regular,
                "price_promo": promo,
                "currency": "MXN",
                "product_url": link["href"] if link else "",
                "category": _first_text(soup, [".breadcrumb", "[data-testid='breadcrumb']"]),
            }
        )

    normalized = []
    for product in products:
        if product.get("product_url") and product["product_url"].startswith("/"):
            product["product_url"] = base_url.rstrip("/") + product["product_url"]
        normalized.append(product)
    return normalized


def _extract_item_list(soup: BeautifulSoup) -> list[dict[str, Any]]:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "ItemList":
            items = data.get("itemListElement", [])
            results = []
            for item in items:
                if isinstance(item, dict):
                    results.append(item.get("item", {}))
            return results
    return []
