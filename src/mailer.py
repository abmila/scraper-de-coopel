import logging
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from src.settings import Settings


LOGGER = logging.getLogger("coppel_scraper")


def _attach_file(message: EmailMessage, path: Path) -> None:
    mime_type, _ = mimetypes.guess_type(path.name)
    maintype, subtype = (mime_type or "application/octet-stream").split("/")
    with path.open("rb") as file:
        message.add_attachment(
            file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )


def send_email(settings: Settings, subject: str, body: str, attachments: Iterable[Path]) -> None:
    if not settings.email_sender or not settings.email_password or not settings.email_to:
        LOGGER.info("Email settings not configured. Skipping email.")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_sender
    message["To"] = settings.email_to
    message.set_content(body)

    for attachment in attachments:
        if attachment.exists():
            _attach_file(message, attachment)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.email_sender, settings.email_password)
            smtp.send_message(message)
        LOGGER.info("Email sent to %s", settings.email_to)
    except Exception as exc:
        LOGGER.error("Failed to send email: %s", exc)
