import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("MODE", "pdp").lower()
    plp_url: str = os.getenv("PLP_URL", "")
    urls_file: str = os.getenv("URLS_FILE", "urls.txt")
    max_urls: int = _get_int("MAX_URLS", 0)
    max_pages: int = _get_int("MAX_PAGES", 50)
    headless: bool = _get_bool("HEADLESS", True)
    slow_mo_ms: int = _get_int("SLOW_MO_MS", 0)
    user_agent: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    locale: str = os.getenv("LOCALE", "es-MX")
    timezone: str = os.getenv("TIMEZONE", "America/Mexico_City")
    nav_timeout_ms: int = _get_int("NAV_TIMEOUT_MS", 45000)
    wait_selector_ms: int = _get_int("WAIT_SELECTOR_MS", 20000)
    max_retries_per_url: int = _get_int("MAX_RETRIES_PER_URL", 3)
    min_sleep_sec: float = _get_float("MIN_SLEEP_SEC", 1.5)
    max_sleep_sec: float = _get_float("MAX_SLEEP_SEC", 3.5)
    debug_save_html: bool = _get_bool("DEBUG_SAVE_HTML", True)
    debug_save_screenshot: bool = _get_bool("DEBUG_SAVE_SCREENSHOT", True)
    output_dir: str = os.getenv("OUTPUT_DIR", "outputs")
    block_images: bool = _get_bool("BLOCK_IMAGES", False)
    dump_html: bool = _get_bool("DUMP_HTML", False)
    max_runtime_sec: int = _get_int("MAX_RUNTIME_SEC", 0)
    enable_stealth: bool = _get_bool("ENABLE_STEALTH", True)
    disable_automation_flags: bool = _get_bool("DISABLE_AUTOMATION_FLAGS", True)
    persistent_context: bool = _get_bool("PERSISTENT_CONTEXT", False)
    persistent_context_dir: str = os.getenv("PERSISTENT_CONTEXT_DIR", "outputs/session")
    enable_stealth: bool = _get_bool("ENABLE_STEALTH", True)
    disable_automation_flags: bool = _get_bool("DISABLE_AUTOMATION_FLAGS", True)

    email_sender: str = os.getenv("EMAIL_SENDER", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    email_to: str = os.getenv("EMAIL_TO", "")
    email_subject: str = os.getenv("EMAIL_SUBJECT", "Coppel scraping report")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = _get_int("SMTP_PORT", 587)

    @property
    def sleep_range(self) -> tuple[float, float]:
        return self.min_sleep_sec, self.max_sleep_sec


def get_settings() -> Settings:
    return Settings()
