import hashlib
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


LOGGER = logging.getLogger("coppel_scraper")


def setup_logging(log_path: Path) -> None:
    LOGGER.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    LOGGER.handlers = [stream_handler, file_handler]


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return cleaned


def parse_price(value: str) -> float | None:
    if not value:
        return None
    raw = re.sub(r"[^0-9,\.]", "", value)
    if raw.count(",") > 1 and raw.count(".") == 0:
        raw = raw.replace(",", "")
    if raw.count(".") > 1 and raw.count(",") == 0:
        raw = raw.replace(".", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw and "." not in raw:
        parts = raw.split(",")
        if len(parts[-1]) == 2:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def hash_key(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def random_sleep(min_sec: float, max_sec: float) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def chunked(items: Iterable[Any], size: int) -> list[list[Any]]:
    bucket = []
    chunked_items = []
    for item in items:
        bucket.append(item)
        if len(bucket) >= size:
            chunked_items.append(bucket)
            bucket = []
    if bucket:
        chunked_items.append(bucket)
    return chunked_items


def parse_headers_json(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.info("Invalid EXTRA_HEADERS_JSON. Ignoring.")
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}
