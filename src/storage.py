import csv
from pathlib import Path
from typing import Any

from openpyxl import Workbook


DEFAULT_COLUMNS = [
    "timestamp_utc",
    "mode",
    "source_url",
    "final_url",
    "product_url",
    "title",
    "price_regular",
    "price_promo",
    "currency",
    "availability",
    "stock_text",
    "seller",
    "brand",
    "model",
    "sku",
    "category",
    "description_short",
    "description_full",
    "description_full_path",
    "images",
    "rating",
    "reviews_count",
    "http_status",
    "page_type_detected",
    "status",
    "error",
    "attempts",
    "elapsed_sec",
]


def _column_order(rows: list[dict[str, Any]]) -> list[str]:
    keys = set(DEFAULT_COLUMNS)
    for row in rows:
        keys.update(row.keys())
    ordered = [col for col in DEFAULT_COLUMNS if col in keys]
    ordered.extend(sorted(keys - set(ordered)))
    return ordered


def save_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = _column_order(rows)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def save_xlsx(rows: list[dict[str, Any]], path: Path) -> None:
    columns = _column_order(rows)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(key, "") for key in columns])
    workbook.save(path)
